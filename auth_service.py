"""Accounts. Students may self-register; staff accounts are created by an administrator only.
Passwords are stored as salted scrypt hashes. Repeated failures lock the account (enforced in the database)."""
import hashlib
import hmac
import logging
import os
import re
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from config import get_settings
from database import connect, transaction
from schemas import User

MAX_ATTEMPTS, LOCK_MINUTES = 5, 5
_SCRYPT = dict(n=2 ** 14, r=8, p=1, dklen=32)
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
GENERIC = "Incorrect email or password."
log = logging.getLogger("resolveai.auth")


class AuthError(Exception):
    """Raised with a message that is safe to show to the person."""


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    return f"scrypt${salt.hex()}${hashlib.scrypt(password.encode(), salt=salt, **_SCRYPT).hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, salt, digest = stored.split("$")
        got = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), **_SCRYPT)
        return hmac.compare_digest(got, bytes.fromhex(digest))
    except (ValueError, TypeError):
        return False


_DUMMY = hash_password("not-a-real-password")  # equalises timing when an email is unknown


def _clean(name: str, email: str, password: str) -> tuple[str, str]:
    name, email = " ".join((name or "").split()), (email or "").strip().lower()
    if not 2 <= len(name) <= 80:
        raise AuthError("Please enter your name (2 to 80 characters).")
    if not _EMAIL.match(email) or len(email) > 120:
        raise AuthError("Please enter a valid email address.")
    if not 8 <= len(password or "") <= 128:
        raise AuthError("Choose a password of at least 8 characters.")
    return name, email


def normalize_phone(phone: str | None) -> str | None:
    """Normalize a worker contact to E.164; blank contacts are allowed."""
    raw = re.sub(r"[\s().-]", "", phone or "")
    if not raw:
        return None
    if not re.fullmatch(r"\+[1-9]\d{7,14}", raw):
        raise AuthError("Enter a valid international phone number, for example +916398758826.")
    return raw


def _create(name, email, password, role, is_demo=False, db_path=None, department=None, phone=None) -> User:
    name, email = _clean(name, email, password)
    try:
        with connect(db_path) as c, transaction(c):
            cur = c.execute("INSERT INTO users (name, email, role, password_hash, created_at, is_demo, department, phone) VALUES (?,?,?,?,?,?,?,?)",
                            (name, email, role, hash_password(password), datetime.now(timezone.utc).isoformat(timespec="seconds"), int(is_demo), department, phone))
            uid = cur.lastrowid
    except sqlite3.IntegrityError as e:
        raise AuthError("An account with this email already exists.") from e
    except sqlite3.Error as e:
        raise AuthError("The account could not be created. Please try again.") from e
    return User(id=uid, name=name, email=email, role=role, department=department)


def register_student(name: str, email: str, password: str, db_path: str | None = None) -> User:
    domains = get_settings().allowed_email_domains
    if domains and (email or "").strip().lower().rsplit("@", 1)[-1] not in domains:
        raise AuthError("Please sign up with your college email address (" + ", ".join("@" + d for d in domains) + ").")
    return _create(name, email, password, "student", db_path=db_path)


def create_staff(name: str, email: str, password: str, is_demo: bool = False, db_path: str | None = None, department: str | None = None) -> User:
    """Administrator-only path: used by create_user.py and the bootstrap setting, never by a public form."""
    return _create(name, email, password, "staff", is_demo=is_demo, db_path=db_path, department=department)


def create_worker(name: str, email: str, password: str, occupation: str, is_demo: bool = False,
                  db_path: str | None = None, phone: str | None = None) -> User:
    """Create a worker account scoped to one campus response occupation/team."""
    from schemas import DEPARTMENTS
    if occupation not in DEPARTMENTS:
        raise AuthError("Choose a valid worker occupation/team.")
    if phone is None:
        phone = get_settings().default_worker_phone
    phone = normalize_phone(phone)
    return _create(name, email, password, "worker", is_demo=is_demo, db_path=db_path, department=occupation, phone=phone)


def update_worker_phone(worker_id: int, phone: str | None, *, actor: User, db_path: str | None = None) -> None:
    if not is_staff(actor.id, db_path):
        raise AuthError("Only staff admins can update worker contacts.")
    phone = normalize_phone(phone)
    with connect(db_path) as c, transaction(c):
        updated = c.execute("UPDATE users SET phone=? WHERE id=? AND role='worker' AND is_active=1", (phone, worker_id)).rowcount
        if not updated:
            raise AuthError("That worker account could not be found.")


def list_worker_contacts(*, actor: User, db_path: str | None = None) -> list[dict]:
    if not is_staff(actor.id, db_path):
        raise AuthError("Only staff admins can view worker contacts.")
    with connect(db_path) as c:
        return [dict(r) for r in c.execute("SELECT id,name,email,department,phone,is_demo,is_active FROM users WHERE role='worker' AND is_active=1 ORDER BY department,name")]


def list_worker_accounts(*, actor: User, db_path: str | None = None) -> list[dict]:
    """Staff-only account management list, including removed accounts for audit visibility."""
    if not is_staff(actor.id, db_path):
        raise AuthError("Only staff admins can manage worker accounts.")
    with connect(db_path) as c:
        return [dict(r) for r in c.execute("SELECT id,name,email,department,phone,is_demo,is_active FROM users WHERE role='worker' ORDER BY is_active DESC,department,name")]


def update_worker_account(worker_id: int, name: str, email: str, occupation: str, phone: str | None,
                          *, actor: User, new_password: str | None = None, db_path: str | None = None) -> None:
    """Update an active worker; changing teams releases their live assignments and revokes sessions."""
    from schemas import DEPARTMENTS, LIVE_STATUSES
    if not is_staff(actor.id, db_path):
        raise AuthError("Only staff admins can update worker accounts.")
    name, email = " ".join((name or "").split()), (email or "").strip().lower()
    if not 2 <= len(name) <= 80:
        raise AuthError("Please enter the worker's name (2 to 80 characters).")
    if not _EMAIL.fullmatch(email) or len(email) > 120:
        raise AuthError("Please enter a valid email address.")
    if occupation not in DEPARTMENTS:
        raise AuthError("Choose a valid worker occupation/team.")
    if new_password and not 8 <= len(new_password) <= 128:
        raise AuthError("Choose a password of at least 8 characters.")
    phone = normalize_phone(phone)
    statuses = tuple(s.value for s in LIVE_STATUSES)
    placeholders = ",".join("?" for _ in statuses)
    try:
        with connect(db_path) as c, transaction(c):
            row = c.execute("SELECT department FROM users WHERE id=? AND role='worker' AND is_active=1", (worker_id,)).fetchone()
            if not row:
                raise AuthError("That active worker account could not be found.")
            previous_team = row["department"]
            password_sql = ", password_hash=?" if new_password else ""
            args = [name, email, occupation, phone]
            if new_password:
                args.append(hash_password(new_password))
            args.append(worker_id)
            c.execute(f"UPDATE users SET name=?, email=?, department=?, phone=?{password_sql}, failed_attempts=0, locked_until=NULL, reset_hash=NULL, reset_expires=NULL WHERE id=?", args)
            if previous_team != occupation:
                tasks = c.execute(f"SELECT ticket_id FROM tickets WHERE assignee_id=? AND status IN ({placeholders})", (worker_id, *statuses)).fetchall()
                now = datetime.now(timezone.utc).isoformat(timespec="seconds")
                for task in tasks:
                    c.execute("UPDATE tickets SET assignee_id=NULL,updated_at=? WHERE ticket_id=?", (now, task["ticket_id"]))
                    c.execute("INSERT INTO ticket_events (ticket_id,actor_id,actor_role,action,detail,created_at) VALUES (?,?,?,?,?,?)",
                              (task["ticket_id"], actor.id, "staff", "assignment", f"unassigned because worker team changed from {previous_team or 'unassigned'} to {occupation}", now))
            # Re-authentication ensures changed identity, occupation or password takes effect immediately.
            c.execute("DELETE FROM sessions WHERE user_id=?", (worker_id,))
    except sqlite3.IntegrityError as e:
        raise AuthError("Another account already uses that email address.") from e
    except sqlite3.Error as e:
        raise AuthError("The worker account could not be updated. Please try again.") from e


def delete_worker_account(worker_id: int, *, actor: User, db_path: str | None = None) -> int:
    """Disable a worker login, clear its SMS phone and release live work while retaining ticket history."""
    from schemas import LIVE_STATUSES
    if not is_staff(actor.id, db_path):
        raise AuthError("Only staff admins can remove worker accounts.")
    statuses = tuple(s.value for s in LIVE_STATUSES)
    placeholders = ",".join("?" for _ in statuses)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        with connect(db_path) as c, transaction(c):
            row = c.execute("SELECT id FROM users WHERE id=? AND role='worker' AND is_active=1", (worker_id,)).fetchone()
            if not row:
                raise AuthError("That active worker account could not be found.")
            tasks = c.execute(f"SELECT ticket_id FROM tickets WHERE assignee_id=? AND status IN ({placeholders})", (worker_id, *statuses)).fetchall()
            c.execute("UPDATE users SET is_active=0,phone=NULL,reset_hash=NULL,reset_expires=NULL,password_hash=? WHERE id=?",
                      (hash_password(secrets.token_urlsafe(32)), worker_id))
            c.execute("DELETE FROM sessions WHERE user_id=?", (worker_id,))
            for task in tasks:
                c.execute("UPDATE tickets SET assignee_id=NULL,updated_at=? WHERE ticket_id=?", (now, task["ticket_id"]))
                c.execute("INSERT INTO ticket_events (ticket_id,actor_id,actor_role,action,detail,created_at) VALUES (?,?,?,?,?,?)",
                          (task["ticket_id"], actor.id, "staff", "assignment", "unassigned because worker account was removed", now))
            return len(tasks)
    except sqlite3.Error as e:
        raise AuthError("The worker account could not be removed. Please try again.") from e


def worker_phone(actor: User, db_path: str | None = None) -> str | None:
    if actor.role != "worker":
        return None
    with connect(db_path) as c:
        row = c.execute("SELECT phone FROM users WHERE id=? AND role='worker' AND is_active=1", (actor.id,)).fetchone()
    return row["phone"] if row else None


def authenticate(email: str, password: str, role: str | None = None, db_path: str | None = None,
                 occupation: str | None = None) -> User:
    email = (email or "").strip().lower()
    now = datetime.now(timezone.utc)
    with connect(db_path) as c:
        row = c.execute("SELECT id, name, email, role, department, password_hash, failed_attempts, locked_until, is_active FROM users WHERE email = ?", (email,)).fetchone()
    if row is None:
        verify_password(password or "", _DUMMY)
        raise AuthError(GENERIC)
    if not row["is_active"]:
        verify_password(password or "", _DUMMY)
        raise AuthError(GENERIC)
    if row["locked_until"] and datetime.fromisoformat(row["locked_until"]) > now:
        raise AuthError(f"Too many unsuccessful attempts. Please try again in {LOCK_MINUTES} minutes.")
    if (not verify_password(password or "", row["password_hash"]) or (role and row["role"] != role)
            or (row["role"] == "worker" and occupation is not None and row["department"] != occupation)
            or (role == "worker" and row["role"] == "worker" and not occupation)):
        fails = row["failed_attempts"] + 1
        lock = (now + timedelta(minutes=LOCK_MINUTES)).isoformat(timespec="seconds") if fails >= MAX_ATTEMPTS else None
        with connect(db_path) as c, transaction(c):
            c.execute("UPDATE users SET failed_attempts = ?, locked_until = ? WHERE id = ?", (0 if lock else fails, lock, row["id"]))
        log.warning("login_failed", extra={"user_id": row["id"], "locked": bool(lock)})  # no email or password in logs
        raise AuthError(GENERIC)  # same message for wrong password and wrong role: no account probing
    with connect(db_path) as c, transaction(c):
        c.execute("UPDATE users SET failed_attempts = 0, locked_until = NULL WHERE id = ?", (row["id"],))
    return User(id=row["id"], name=row["name"], email=row["email"], role=row["role"], department=row["department"])


def ensure_bootstrap_staff(db_path: str | None = None) -> bool:
    """If STAFF_EMAIL and STAFF_PASSWORD are set and no staff account exists, create the first one."""
    s = get_settings()
    if not (s.staff_email and s.staff_password):
        return False
    with connect(db_path) as c:
        if c.execute("SELECT 1 FROM users WHERE role = 'staff' LIMIT 1").fetchone():
            return False
    try:
        create_staff("Staff Admin", s.staff_email, s.staff_password, db_path=db_path)
        return True
    except AuthError:
        return False


# ---------------------------------------------------------------- roles, sessions, password reset
SESSION_HOURS, RESET_MINUTES = 8, 30


def _h(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def is_staff(user_id: int, db_path: str | None = None) -> bool:
    with connect(db_path) as c:
        row = c.execute("SELECT role,is_active FROM users WHERE id = ?", (user_id,)).fetchone()
    return bool(row and row["role"] == "staff" and row["is_active"])


def is_worker(user_id: int, db_path: str | None = None) -> bool:
    with connect(db_path) as c:
        row = c.execute("SELECT role,is_active FROM users WHERE id = ?", (user_id,)).fetchone()
    return bool(row and row["role"] == "worker" and row["is_active"])


def is_staff_or_worker(user_id: int, db_path: str | None = None) -> bool:
    with connect(db_path) as c:
        row = c.execute("SELECT role,is_active FROM users WHERE id = ?", (user_id,)).fetchone()
    return bool(row and row["role"] in ("staff", "worker") and row["is_active"])


def create_session(user_id: int, db_path: str | None = None) -> str:
    """Server-side session. Only a hash of the token is stored; it expires and is revoked on sign-out."""
    token, now = secrets.token_urlsafe(32), datetime.now(timezone.utc)
    with connect(db_path) as c, transaction(c):
        if not c.execute("SELECT 1 FROM users WHERE id=? AND is_active=1", (user_id,)).fetchone():
            raise AuthError(GENERIC)
        c.execute("DELETE FROM sessions WHERE expires_at < ?", (now.isoformat(timespec="seconds"),))
        c.execute("INSERT INTO sessions (token_hash, user_id, created_at, expires_at) VALUES (?,?,?,?)",
                  (_h(token), user_id, now.isoformat(timespec="seconds"), (now + timedelta(hours=SESSION_HOURS)).isoformat(timespec="seconds")))
    return token


def user_from_session(token: str | None, db_path: str | None = None) -> User | None:
    if not token or len(token) > 100:
        return None
    with connect(db_path) as c:
        row = c.execute("SELECT u.id, u.name, u.email, u.role, u.department, u.is_active, s.expires_at FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token_hash = ?", (_h(token),)).fetchone()
    if not row or not row["is_active"] or datetime.fromisoformat(row["expires_at"]) <= datetime.now(timezone.utc):
        return None
    return User(id=row["id"], name=row["name"], email=row["email"], role=row["role"], department=row["department"])


def end_session(token: str | None, db_path: str | None = None) -> None:
    if token:
        with connect(db_path) as c, transaction(c):
            c.execute("DELETE FROM sessions WHERE token_hash = ?", (_h(token),))


def issue_reset_code(email: str, *, actor: User, db_path: str | None = None) -> str:
    """Staff issue a one-time code to a student who forgot their password. Shown once, valid 30 minutes."""
    if not is_staff(actor.id, db_path):
        raise AuthError("Only staff admins can issue reset codes.")
    email = (email or "").strip().lower()
    with connect(db_path) as c:
        row = c.execute("SELECT id FROM users WHERE email = ? AND role IN ('student','worker') AND is_active=1", (email,)).fetchone()
    if not row:
        raise AuthError("No student or worker account uses that email.")
    raw = secrets.token_hex(4).upper()
    code = f"{raw[:4]}-{raw[4:]}"
    with connect(db_path) as c, transaction(c):
        c.execute("UPDATE users SET reset_hash = ?, reset_expires = ? WHERE id = ?",
                  (_h(raw), (datetime.now(timezone.utc) + timedelta(minutes=RESET_MINUTES)).isoformat(timespec="seconds"), row["id"]))
    return code


def redeem_reset(email: str, code: str, new_password: str, db_path: str | None = None) -> None:
    bad = AuthError("That reset code is not valid or has expired.")
    if not 8 <= len(new_password or "") <= 128:
        raise AuthError("Choose a password of at least 8 characters.")
    email, now = (email or "").strip().lower(), datetime.now(timezone.utc)
    with connect(db_path) as c:
        row = c.execute("SELECT id, reset_hash, reset_expires, failed_attempts, locked_until, is_active FROM users WHERE email = ?", (email,)).fetchone()
    if not row or not row["is_active"] or not row["reset_hash"]:
        raise bad
    if row["locked_until"] and datetime.fromisoformat(row["locked_until"]) > now:
        raise AuthError(f"Too many unsuccessful attempts. Please try again in {LOCK_MINUTES} minutes.")
    ok = hmac.compare_digest(row["reset_hash"], _h("".join(ch for ch in (code or "").upper() if ch.isalnum()))) and datetime.fromisoformat(row["reset_expires"]) > now
    if not ok:
        fails = row["failed_attempts"] + 1
        lock = (now + timedelta(minutes=LOCK_MINUTES)).isoformat(timespec="seconds") if fails >= MAX_ATTEMPTS else None
        with connect(db_path) as c, transaction(c):
            c.execute("UPDATE users SET failed_attempts = ?, locked_until = ? WHERE id = ?", (0 if lock else fails, lock, row["id"]))
        raise bad
    with connect(db_path) as c, transaction(c):  # single use; sign out everywhere; clear lockout
        c.execute("UPDATE users SET password_hash = ?, reset_hash = NULL, reset_expires = NULL, failed_attempts = 0, locked_until = NULL WHERE id = ?",
                  (hash_password(new_password), row["id"]))
        c.execute("DELETE FROM sessions WHERE user_id = ?", (row["id"],))


def set_password(email: str, new_password: str, db_path: str | None = None) -> None:
    """Administrator-only (command line): set any account's password, e.g. a forgotten staff password."""
    if not 8 <= len(new_password or "") <= 128:
        raise AuthError("Choose a password of at least 8 characters.")
    with connect(db_path) as c, transaction(c):
        n = c.execute("UPDATE users SET password_hash = ?, failed_attempts = 0, locked_until = NULL, reset_hash = NULL, reset_expires = NULL WHERE email = ?",
                      (hash_password(new_password), (email or "").strip().lower())).rowcount
        if not n:
            raise AuthError("No account uses that email.")
        c.execute("DELETE FROM sessions WHERE user_id = (SELECT id FROM users WHERE email = ?)", ((email or "").strip().lower(),))


def is_student(user_id: int, db_path: str | None = None) -> bool:
    with connect(db_path) as c:
        row = c.execute("SELECT role FROM users WHERE id = ?", (user_id,)).fetchone()
    return bool(row and row["role"] == "student")


DEMO_PASSWORD = "DemoPass123"
DEMO_ACCOUNTS = [("Alex Rivera", "student@demo.test", "student", None), ("Mario Vance", "plumbing@demo.test", "staff", "Plumbing"),
                 ("Sarah Connor", "it@demo.test", "staff", "IT/Network Support"), ("Taylor Reed", "worker@demo.test", "worker", "Electrical Maintenance"),
                 ("Chief Admin", "admin@demo.test", "staff", None)]

DEMO_WORKER_ACCOUNTS = [
    ("Taylor Reed", "worker@demo.test", "Electrical Maintenance"),
    ("IT Worker", "worker.it@demo.test", "IT/Network Support"),
    ("Plumbing Worker", "worker.plumbing@demo.test", "Plumbing"),
    ("Hostel Worker", "worker.hostel@demo.test", "Hostel Maintenance"),
    ("Lab Worker", "worker.lab@demo.test", "Equipment/Lab Support"),
    ("Campus Assistant", "worker.admin@demo.test", "General Administration"),
    ("Safety Responder", "worker.safety@demo.test", "Campus Safety & Emergency Response"),
]


def ensure_demo_accounts(db_path: str | None = None) -> bool:
    """Only when DEMO_MODE=1: create one-click demo logins. Their password is published, so never enable this on a real deployment."""
    if not get_settings().demo_mode:
        return False
    for name, email, role, dept in DEMO_ACCOUNTS:
        try:
            _create(name, email, DEMO_PASSWORD, role, is_demo=True, db_path=db_path, department=dept)
        except AuthError:
            pass  # already exists
    for name, email, occupation in DEMO_WORKER_ACCOUNTS:
        try:
            create_worker(name, email, DEMO_PASSWORD, occupation, is_demo=True, db_path=db_path)
        except AuthError:
            # Do not overwrite existing account credentials or change its team.
            with connect(db_path) as c, transaction(c):
                c.execute("UPDATE users SET is_demo=1, phone=COALESCE(phone, ?) WHERE email=? AND role='worker' AND department=?",
                          (get_settings().default_worker_phone, email, occupation))
    return True
