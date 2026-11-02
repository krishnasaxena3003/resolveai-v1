"""SQLite connection, schema and versioned migrations. All writes go through explicit transactions."""
import sqlite3
from pathlib import Path
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from config import get_settings
from schemas import Category, Priority, Status

LATEST_VERSION = 16  # v16 supports worker account deactivation and assignment-safe removal
BUSY_TIMEOUT_MS = 10_000
_q = lambda e: ",".join(f"'{m.value}'" for m in e)


def _tickets_ddl(name: str, if_not_exists: bool = True) -> str:
    return f"""CREATE TABLE {'IF NOT EXISTS ' if if_not_exists else ''}{name} (
  ticket_id TEXT PRIMARY KEY,
  description TEXT NOT NULL CHECK (length(trim(description)) > 0),
  summary TEXT NOT NULL,
  category TEXT NOT NULL CHECK (category IN ({_q(Category)})),
  priority TEXT NOT NULL CHECK (priority IN ({_q(Priority)})),
  department TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'Open' CHECK (status IN ({_q(Status)})),
  location TEXT,
  location_id TEXT REFERENCES campus_locations(location_id),
  duplicate_of TEXT REFERENCES tickets(ticket_id),
  review_required INTEGER NOT NULL DEFAULT 0,
  ai_mode TEXT NOT NULL CHECK (ai_mode IN ('llm','fallback')),
  tracking_hash TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  resolution_note TEXT,
  is_sample INTEGER NOT NULL DEFAULT 0,
  reporter_id INTEGER REFERENCES users(id),
  is_anonymous INTEGER NOT NULL DEFAULT 0,
  critical_alert INTEGER NOT NULL DEFAULT 0,
  assignee_id INTEGER REFERENCES users(id),
  resolved_at TEXT,
  fixed_at TEXT,
  resolved_by TEXT,
  rating INTEGER CHECK (rating IS NULL OR rating BETWEEN 1 AND 5),
  reopen_count INTEGER NOT NULL DEFAULT 0,
  withdrawal_review INTEGER NOT NULL DEFAULT 0,
  withdrawal_reason TEXT,
  staff_removed INTEGER NOT NULL DEFAULT 0,
  staff_removal_reason TEXT,
  deadline_at TEXT
)"""


_TICKET_INDEXES = ["CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status)", "CREATE INDEX IF NOT EXISTS idx_tickets_category ON tickets(category)",
                   "CREATE INDEX IF NOT EXISTS idx_tickets_reporter ON tickets(reporter_id)", "CREATE INDEX IF NOT EXISTS idx_tickets_assignee ON tickets(assignee_id)",
                   "CREATE INDEX IF NOT EXISTS idx_tickets_created ON tickets(created_at DESC, ticket_id DESC)",
                   "CREATE INDEX IF NOT EXISTS idx_tickets_status_created ON tickets(status, created_at DESC, ticket_id DESC)",
                   "CREATE INDEX IF NOT EXISTS idx_tickets_reporter_created ON tickets(reporter_id, created_at DESC, ticket_id DESC)",
                   "CREATE INDEX IF NOT EXISTS idx_tickets_assignee_created ON tickets(assignee_id, created_at DESC, ticket_id DESC)",
                   "CREATE INDEX IF NOT EXISTS idx_tickets_duplicate ON tickets(duplicate_of)",
                   "CREATE INDEX IF NOT EXISTS idx_tickets_withdrawal_review ON tickets(status, withdrawal_review, updated_at DESC)",
                   "CREATE INDEX IF NOT EXISTS idx_tickets_critical_status_deadline ON tickets(critical_alert, status, deadline_at)"]
_USER_INDEXES = ["CREATE INDEX IF NOT EXISTS idx_users_worker_alert_recipients ON users(role, department, is_demo, phone)",
                 "CREATE INDEX IF NOT EXISTS idx_users_active_worker_alert_recipients ON users(role, department, is_active, is_demo, phone)"]
SCHEMA = f"""
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  email TEXT NOT NULL UNIQUE COLLATE NOCASE,
  role TEXT NOT NULL CHECK (role IN ('student','staff','worker')),
  password_hash TEXT NOT NULL,
  failed_attempts INTEGER NOT NULL DEFAULT 0,
  locked_until TEXT,
  created_at TEXT NOT NULL,
  is_demo INTEGER NOT NULL DEFAULT 0,
  reset_hash TEXT,
  reset_expires TEXT,
  department TEXT,
  phone TEXT,
  is_active INTEGER NOT NULL DEFAULT 1
);
{_tickets_ddl('tickets')};
CREATE TABLE IF NOT EXISTS attachments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ticket_id TEXT NOT NULL REFERENCES tickets(ticket_id),
  kind TEXT NOT NULL CHECK (kind IN ('report','resolution')),
  uploader_id INTEGER,
  original_name TEXT NOT NULL,
  stored_name TEXT NOT NULL UNIQUE,
  content_type TEXT NOT NULL,
  size_bytes INTEGER NOT NULL,
  width INTEGER,
  height INTEGER,
  sha256 TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_attachments_ticket ON attachments(ticket_id);
CREATE TABLE IF NOT EXISTS sessions (
  token_hash TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ticket_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ticket_id TEXT NOT NULL REFERENCES tickets(ticket_id),
  actor_id INTEGER,
  actor_role TEXT NOT NULL,
  action TEXT NOT NULL,
  detail TEXT,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_ticket ON ticket_events(ticket_id);
CREATE TABLE IF NOT EXISTS academic_departments (
  department_id TEXT PRIMARY KEY, display_name TEXT NOT NULL UNIQUE, source_url TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS academic_department_aliases (
  alias TEXT PRIMARY KEY COLLATE NOCASE, department_id TEXT NOT NULL REFERENCES academic_departments(department_id)
);
CREATE TABLE IF NOT EXISTS campus_locations (
  location_id TEXT PRIMARY KEY, display_name TEXT NOT NULL, canonical_name TEXT NOT NULL UNIQUE,
  location_type TEXT NOT NULL CHECK (location_type IN ('campus','building','facility','floor','room')),
  latitude REAL, longitude REAL, parent_location_id TEXT REFERENCES campus_locations(location_id),
  academic_department_id TEXT REFERENCES academic_departments(department_id), coordinate_source TEXT,
  verification_status TEXT NOT NULL DEFAULT 'unverified', last_verified_at TEXT,
  google_maps_url TEXT, source_url TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  CHECK ((latitude IS NULL AND longitude IS NULL) OR (latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180))
);
CREATE INDEX IF NOT EXISTS idx_campus_locations_parent ON campus_locations(parent_location_id);
CREATE INDEX IF NOT EXISTS idx_campus_locations_type ON campus_locations(location_type);
CREATE TABLE IF NOT EXISTS lookup_attempts (
  ticket_key TEXT PRIMARY KEY,
  failed INTEGER NOT NULL DEFAULT 0,
  locked_until TEXT
);
CREATE TABLE IF NOT EXISTS ticket_comments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ticket_id TEXT NOT NULL REFERENCES tickets(ticket_id),
  author_id INTEGER NOT NULL,
  visibility TEXT NOT NULL CHECK (visibility IN ('internal','public')),
  body TEXT NOT NULL CHECK (length(trim(body)) > 0),
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_comments_ticket ON ticket_comments(ticket_id);
CREATE TABLE IF NOT EXISTS rate_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  kind TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_rate_user_kind ON rate_events(user_id, kind, created_at);
CREATE TABLE IF NOT EXISTS schema_version (
  version INTEGER NOT NULL,
  applied_at TEXT NOT NULL
);
"""
_ADDED_COLUMNS = [("users", "reset_hash", "TEXT"), ("users", "reset_expires", "TEXT"), ("users", "department", "TEXT"), ("users", "phone", "TEXT"), ("users", "is_active", "INTEGER NOT NULL DEFAULT 1"), ("tickets", "reporter_id", "INTEGER"),
                  ("tickets", "is_anonymous", "INTEGER NOT NULL DEFAULT 0"),
                  ("tickets", "critical_alert", "INTEGER NOT NULL DEFAULT 0"),
                  ("tickets", "assignee_id", "INTEGER"), ("tickets", "resolved_at", "TEXT"), ("tickets", "fixed_at", "TEXT"), ("tickets", "resolved_by", "TEXT"),
                  ("tickets", "rating", "INTEGER"), ("tickets", "reopen_count", "INTEGER NOT NULL DEFAULT 0"), ("tickets", "withdrawal_review", "INTEGER NOT NULL DEFAULT 0"),
                  ("tickets", "withdrawal_reason", "TEXT"),
                  ("tickets", "staff_removed", "INTEGER NOT NULL DEFAULT 0"),
                  ("tickets", "staff_removal_reason", "TEXT"),
                  ("tickets", "deadline_at", "TEXT"),
                  ("tickets", "location_id", "TEXT REFERENCES campus_locations(location_id)"),
                  ("campus_locations", "source_url", "TEXT")]
COLUMNS = ("ticket_id, description, summary, category, priority, department, status, location, duplicate_of, review_required, "
           "ai_mode, created_at, updated_at, resolution_note, is_sample, reporter_id, is_anonymous, critical_alert, assignee_id, resolved_at, fixed_at, resolved_by, rating, reopen_count, withdrawal_review, withdrawal_reason, location_id, staff_removed, staff_removal_reason, deadline_at")


@contextmanager
def connect(db_path: str | None = None):
    conn = sqlite3.connect(db_path or get_settings().db_path, timeout=BUSY_TIMEOUT_MS / 1000, isolation_level=None)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
        yield conn
    finally:
        conn.close()


@contextmanager
def transaction(conn):
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise


def _rebuild_tickets_if_needed(conn) -> None:
    """SQLite cannot alter a CHECK constraint, so databases from before the sign-off lifecycle are rebuilt (SQLite's documented procedure)."""
    row = conn.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'tickets'").fetchone()
    if not row or ("'Pending Sign-off'" in row[0] and "'Withdrawn'" in row[0]):
        return
    old = [r[1] for r in conn.execute("PRAGMA table_info(tickets)")]
    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        conn.execute("BEGIN")
        conn.execute(_tickets_ddl("tickets_new", False))
        new = {r[1] for r in conn.execute("PRAGMA table_info(tickets_new)")}
        keep = ", ".join(c for c in old if c in new)
        conn.execute(f"INSERT INTO tickets_new ({keep}) SELECT {keep} FROM tickets")
        conn.execute("DROP TABLE tickets")
        conn.execute("ALTER TABLE tickets_new RENAME TO tickets")
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.execute("PRAGMA foreign_keys = ON")


def _rebuild_users_for_worker_role(conn) -> None:
    """Add the worker role while preserving existing user IDs and all foreign-key links."""
    row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='users'").fetchone()
    if not row or "'worker'" in row[0]:
        return
    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        conn.execute("BEGIN")
        conn.execute("""CREATE TABLE users_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE COLLATE NOCASE,
            role TEXT NOT NULL CHECK (role IN ('student','staff','worker')),
            password_hash TEXT NOT NULL,
            failed_attempts INTEGER NOT NULL DEFAULT 0,
            locked_until TEXT,
            created_at TEXT NOT NULL,
            is_demo INTEGER NOT NULL DEFAULT 0,
            reset_hash TEXT,
            reset_expires TEXT,
            department TEXT,
            phone TEXT,
            is_active INTEGER NOT NULL DEFAULT 1
        )""")
        cols = ["id", "name", "email", "role", "password_hash", "failed_attempts", "locked_until", "created_at", "is_demo", "reset_hash", "reset_expires", "department", "phone", "is_active"]
        keep = ",".join(cols)
        conn.execute(f"INSERT INTO users_new ({keep}) SELECT {keep} FROM users")
        conn.execute("DROP TABLE users")
        conn.execute("ALTER TABLE users_new RENAME TO users")
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.execute("PRAGMA foreign_keys = ON")


def schema_version(db_path: str | None = None) -> int:
    with connect(db_path) as c:
        try:
            return c.execute("SELECT COALESCE(MAX(version), 0) FROM schema_version").fetchone()[0]
        except sqlite3.OperationalError:
            return 0


def init_db(db_path: str | None = None) -> None:
    """Create or upgrade the database. Safe to call on every start. Refuses to run against a newer schema."""
    with connect(db_path) as conn:
        # WAL is persistent in the database file. Only switch once; setting it on every
        # Streamlit rerun creates avoidable write-lock contention.
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0].lower()
        if mode != "wal":
            conn.execute("PRAGMA journal_mode = WAL")
        current = 0
        try:
            current = conn.execute("SELECT COALESCE(MAX(version), 0) FROM schema_version").fetchone()[0]
        except sqlite3.OperationalError:
            pass
        if current > LATEST_VERSION:
            raise RuntimeError(f"Database schema v{current} is newer than this app (v{LATEST_VERSION}). Upgrade the app.")
        if current < LATEST_VERSION:
            has_saved_tickets = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='tickets'").fetchone()
            if has_saved_tickets and conn.execute("SELECT 1 FROM tickets LIMIT 1").fetchone():
                target_db = db_path or get_settings().db_path
                backup_dir = Path(target_db).resolve().parent / ".migration_backups"
                backup_dir.mkdir(parents=True, exist_ok=True)
                # Reuse a completed snapshot for retries; the data has not changed since this migration started.
                if not list(backup_dir.glob("resolveai-*.db")):
                    from backup import make_backup
                    make_backup(target_db, str(backup_dir), keep=1)
        conn.executescript(SCHEMA)
        for table, col, decl in _ADDED_COLUMNS:  # upgrade databases created by older versions
            if col not in {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")
        _rebuild_users_for_worker_role(conn)
        _rebuild_tickets_if_needed(conn)
        if current < 10:
            settings = get_settings()
            hours = {Priority.HIGH: settings.sla_high_hours, Priority.MEDIUM: settings.sla_medium_hours,
                     Priority.LOW: settings.sla_low_hours}
            for ticket in conn.execute("SELECT ticket_id, created_at, priority FROM tickets WHERE deadline_at IS NULL").fetchall():
                created = datetime.fromisoformat(ticket["created_at"])
                if created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
                deadline = created + timedelta(hours=hours[Priority(ticket["priority"])])
                conn.execute("UPDATE tickets SET deadline_at=? WHERE ticket_id=? AND deadline_at IS NULL",
                             (deadline.isoformat(timespec="seconds"), ticket["ticket_id"]))
        from campus_catalog import seed_catalog
        seed_catalog(conn)
        # Backfill only exact normalized name matches. Preserve the original free-text value.
        conn.execute("""UPDATE tickets SET location_id=(SELECT location_id FROM campus_locations l
            WHERE lower(trim(l.display_name))=lower(trim(tickets.location)) LIMIT 1)
            WHERE location_id IS NULL AND location IS NOT NULL AND EXISTS
            (SELECT 1 FROM campus_locations l WHERE lower(trim(l.display_name))=lower(trim(tickets.location)))""")
        for idx in _TICKET_INDEXES:
            conn.execute(idx)
        for idx in _USER_INDEXES:
            conn.execute(idx)
        if current < LATEST_VERSION:
            conn.execute("INSERT INTO schema_version (version, applied_at) VALUES (?, ?)", (LATEST_VERSION, datetime.now(timezone.utc).isoformat(timespec="seconds")))
