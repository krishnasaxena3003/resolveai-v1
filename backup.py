"""Consistent online backup of the SQLite database. Run from cron: python backup.py --dir backups --keep 14
Restore: stop the app, copy a backup file over resolveai.db, start the app."""
import argparse
import pathlib
import sqlite3
from datetime import datetime, timezone
from config import get_settings


def make_backup(db_path: str, dest_dir: str, keep: int = 14) -> pathlib.Path:
    if keep < 1:
        raise ValueError("keep must be at least 1")
    source = pathlib.Path(db_path)
    if not source.is_file():
        raise FileNotFoundError(f"Database file not found: {source}")
    dest = pathlib.Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    target = dest / f"resolveai-{datetime.now(timezone.utc):%Y%m%dT%H%M%S%f}.db"
    temporary = target.with_suffix(target.suffix + ".tmp")
    try:
        src = sqlite3.connect(source, timeout=10)
        out = None
        try:
            out = sqlite3.connect(temporary, timeout=10)
            src.backup(out)  # safe while the app is running
            result = out.execute("PRAGMA integrity_check").fetchone()
            if not result or result[0] != "ok":
                raise sqlite3.DatabaseError("The backup did not pass SQLite integrity_check.")
        finally:
            if out is not None:
                out.close()
            src.close()
        temporary.replace(target)  # publish only a complete, verified backup
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    for old in sorted(dest.glob("resolveai-*.db"))[:-keep]:
        old.unlink()
    return target


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="backups"); ap.add_argument("--keep", type=int, default=14); ap.add_argument("--db", default=get_settings().db_path)
    a = ap.parse_args()
    print("Backup written to", make_backup(a.db, a.dir, a.keep))
