"""Operational health. CLI: python healthcheck.py  (exit code 1 when unhealthy; used by Docker and CI)."""
import json
import os
import sys
from config import get_settings
from database import LATEST_VERSION, connect, schema_version


def check(db_path: str | None = None) -> dict:
    s, issues, info = get_settings(), [], {}
    try:
        with connect(db_path) as c:
            info["tickets"] = c.execute("SELECT COUNT(*) FROM tickets").fetchone()[0]
            info["staff_accounts"] = c.execute("SELECT COUNT(*) FROM users WHERE role='staff'").fetchone()[0]
            info["worker_accounts"] = c.execute("SELECT COUNT(*) FROM users WHERE role='worker' AND is_active=1").fetchone()[0]
            info["student_accounts"] = c.execute("SELECT COUNT(*) FROM users WHERE role='student'").fetchone()[0]
        info["schema_version"] = schema_version(db_path)
        if info["schema_version"] != LATEST_VERSION:
            issues.append(f"schema is v{info['schema_version']}, app expects v{LATEST_VERSION}")
        if info["staff_accounts"] == 0:
            issues.append("no staff account exists (set STAFF_EMAIL/STAFF_PASSWORD or run create_user.py)")
    except Exception as e:  # report, never crash the check
        info["db_error"] = type(e).__name__
        issues.append("database unreachable")
    if s.demo_mode:
        issues.append("DEMO_MODE is on: demo accounts share a published password. Turn it off for real use.")
    info["ai_configured"] = bool(s.api_key)
    if not s.api_key:
        issues.append("AI is not configured: reports use labelled fallback rules")
    info["database_path_writable"] = os.access(os.path.dirname(os.path.abspath(db_path or s.db_path)), os.W_OK)
    if not info["database_path_writable"]:
        issues.append("database folder is not writable")
    return {"ok": "database unreachable" not in issues and info["database_path_writable"] and info.get("schema_version") == LATEST_VERSION, "issues": issues, **info}


if __name__ == "__main__":
    r = check()
    print(json.dumps(r, indent=1))
    sys.exit(0 if r["ok"] else 1)
