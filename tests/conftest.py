import sys, pathlib
from types import SimpleNamespace
import pytest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from database import init_db


class FakeClient:
    """Stands in for the OpenAI-compatible client. Replies are strings or Exceptions."""
    def __init__(self, replies):
        self.replies, self.calls, self.last_messages = list(replies), 0, None
        self.chat = SimpleNamespace(completions=self)

    def create(self, **kw):
        self.calls += 1
        self.last_messages = kw["messages"]
        r = self.replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=r))])


@pytest.fixture
def db(tmp_path, monkeypatch):
    path = str(tmp_path / "t.db")
    monkeypatch.setenv("DB_PATH", path)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    init_db(path)
    return path


# ---- staff-actor wrappers: staff-only service functions require a real staff account in the database
import ticket_service as _ts
from auth_service import create_staff

_staff_cache = {}


def staff_for(db_path):
    if db_path not in _staff_cache:
        _staff_cache[db_path] = create_staff("Test Staff", f"staff{len(_staff_cache)}@t.edu", "staff-password-1", db_path=db_path)
    return _staff_cache[db_path]


def update_status(*a, db_path, **k):
    return _ts.update_status(*a, actor=staff_for(db_path), db_path=db_path, **k)


def correct_fields(*a, db_path, **k):
    return _ts.correct_fields(*a, actor=staff_for(db_path), db_path=db_path, **k)


def set_duplicate_link(*a, db_path, **k):
    return _ts.set_duplicate_link(*a, actor=staff_for(db_path), db_path=db_path, **k)


def force_status(db_path, ticket_id, status):
    """Test shortcut: put a ticket in a state directly, bypassing the workflow under test elsewhere."""
    import sqlite3
    with sqlite3.connect(db_path) as conn:
        conn.execute("UPDATE tickets SET status = ? WHERE ticket_id = ?", (getattr(status, "value", status), ticket_id))


def fix_and_confirm(db_path, ticket_id, student, note="Replaced the faulty fuse and tested.", rating=None):
    """Walk the real lifecycle: staff start work and mark fixed, then the student confirms."""
    from schemas import Status
    st = staff_for(db_path)
    _ts.update_status(ticket_id, Status.IN_PROGRESS, actor=st, db_path=db_path)
    _ts.mark_fixed(ticket_id, note, actor=st, db_path=db_path)
    return _ts.student_signoff(ticket_id, actor=student, confirm=True, rating=rating, db_path=db_path)
