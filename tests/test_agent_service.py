import json
from types import SimpleNamespace

import pytest

from agent_service import AgentResponse, TOOLS, execute_tool, investigate
from ai_service import fallback_analysis
from auth_service import register_student
from conftest import staff_for
from ticket_service import create_ticket


def ticket(db, text="No electricity in Hostel Block B"):
    return create_ticket(fallback_analysis(text), text, "Hostel Block B", "fallback", db_path=db).ticket


def test_tools_return_snapshot_related_and_stats_from_database(db):
    first = ticket(db)
    ticket(db, "Power cut in Hostel Block B")
    staff = staff_for(db)
    snap = execute_tool("ticket_snapshot", {"ticket_id": first.ticket_id}, staff)
    related = execute_tool("related_reports", {"ticket_id": first.ticket_id}, staff)
    stats = execute_tool("campus_issue_statistics", {"category": "Electricity"}, staff)
    assert snap["ticket_id"] == first.ticket_id and "description" not in snap
    assert len(related) == 1
    assert stats["count"] == 2 and stats["exclusions"] == ["withdrawn", "sample"]


def test_tool_validation_permissions_and_catalog(db):
    staff = staff_for(db)
    student = register_student("Student User", "student@t.edu", "student-pass-1", db_path=db)
    assert execute_tool("search_campus_locations", {"search_term": "Library"}, staff) is not None
    with pytest.raises(ValueError): execute_tool("not_registered", {}, staff)
    with pytest.raises(ValueError): execute_tool("ticket_snapshot", {"ticket_id": "x", "sql": "drop"}, staff)
    with pytest.raises(PermissionError): execute_tool("campus_issue_statistics", {}, student)


class ToolCall:
    def __init__(self, name, args):
        self.id = "call-1"
        self.function = SimpleNamespace(name=name, arguments=json.dumps(args))


class Message:
    def __init__(self, content=None, calls=None):
        self.content, self.tool_calls = content, calls
    def model_dump(self, **kwargs):
        return {"role": "assistant", "content": self.content, "tool_calls": []}


class Client:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.chat = SimpleNamespace(completions=self)
    def create(self, **kwargs):
        msg = next(self.responses)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


def final_json(tid):
    return json.dumps({"answer": "The ticket is recorded.", "findings": ["Ticket is open."], "evidence": [tid],
        "related_tickets": [], "recommendations": ["Review with the service team."], "uncertainties": [],
        "actions_taken": [], "requires_human_review": True, "status": "success"})


def test_agent_calls_tool_then_validates_response(db, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    t, staff = ticket(db), staff_for(db)
    client = Client([Message(calls=[ToolCall("ticket_snapshot", {"ticket_id": t.ticket_id})]), Message(final_json(t.ticket_id))])
    response, history = investigate(t.ticket_id, staff, "What is its status?", client=client)
    assert isinstance(response, AgentResponse)
    assert response.status == "success" and response.evidence == [t.ticket_id]
    assert len(history) <= 10


def test_agent_rejects_malformed_response_and_limits_history_config(db, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    t, staff = ticket(db), staff_for(db)
    response = investigate(t.ticket_id, staff, client=Client([Message("not json")]))
    assert response.status == "partial" and response.requires_human_review
    assert all(tool["function"]["name"] for tool in TOOLS)
