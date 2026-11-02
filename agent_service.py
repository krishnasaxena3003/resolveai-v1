"""Bounded, staff-authorized, read-only campus investigation orchestration."""
import json
import logging
import time
from datetime import date
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from agent_prompts import SYSTEM_PROMPT
from auth_service import is_staff
from config import get_settings
from database import connect
from schemas import Category, Status, User
from ticket_service import get_ticket, get_timeline, list_tickets

log = logging.getLogger("resolveai.agent")


class AgentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer: str = Field(max_length=3000)
    findings: list[str] = Field(default_factory=list, max_length=20)
    evidence: list[str] = Field(default_factory=list, max_length=30)
    related_tickets: list[str] = Field(default_factory=list, max_length=20)
    recommendations: list[str] = Field(default_factory=list, max_length=15)
    uncertainties: list[str] = Field(default_factory=list, max_length=15)
    actions_taken: list[str] = Field(default_factory=list, max_length=10)
    requires_human_review: bool = False
    status: str = "success"

    @classmethod
    def validate_output(cls, value):
        obj = cls.model_validate(value)
        if obj.status not in {"success", "partial", "unavailable"}:
            raise ValueError("Invalid result status")
        # This agent is intentionally read-only.
        obj.actions_taken = []
        return obj


def _schema(name, description, properties, required):
    return {"type": "function", "function": {"name": name, "description": description,
        "parameters": {"type": "object", "properties": properties, "required": required, "additionalProperties": False}}}

_ID = {"type": "string", "minLength": 1, "maxLength": 32}
TOOLS = [
    _schema("ticket_snapshot", "Read permitted current fields for one real ticket.", {"ticket_id": _ID}, ["ticket_id"]),
    _schema("related_reports", "Find up to 20 non-withdrawn related reports for a ticket.", {"ticket_id": _ID}, ["ticket_id"]),
    _schema("ticket_history", "Read permitted non-internal timeline for a ticket.", {"ticket_id": _ID}, ["ticket_id"]),
    _schema("search_campus_locations", "Search the verified campus location catalog.", {"search_term": {"type":"string","maxLength":100}, "location_type": {"type":"string","enum":["campus","building","facility","floor","department"]}}, ["search_term"]),
    _schema("campus_issue_statistics", "Count actual non-sample, non-withdrawn tickets using optional bounded filters.", {"category":{"type":"string","enum":[x.value for x in Category]}, "status":{"type":"string","enum":[x.value for x in Status if x != Status.WITHDRAWN]}, "location":{"type":"string","maxLength":100}, "date_from":{"type":"string","format":"date"}, "date_to":{"type":"string","format":"date"}}, []),
    _schema("list_related_open_issues", "List up to 20 actual unresolved non-sample issues, optionally filtered by location/category.", {"location":{"type":"string","maxLength":100}, "category":{"type":"string","enum":[x.value for x in Category]}}, []),
]
_ALLOWED = {t["function"]["name"] for t in TOOLS}


def _staff(actor):
    if not isinstance(actor, User) or not is_staff(actor.id):
        raise PermissionError("Staff authorization required")


def execute_tool(name, args, actor):
    _staff(actor)
    if name not in _ALLOWED:
        raise ValueError("Unknown tool")
    if not isinstance(args, dict):
        raise ValueError("Arguments must be an object")
    props = next(t["function"]["parameters"] for t in TOOLS if t["function"]["name"] == name)
    allowed = set(props["properties"])
    if set(args) - allowed:
        raise ValueError("Unexpected tool argument")
    if name in {"ticket_snapshot", "related_reports", "ticket_history"} and (set(args) != {"ticket_id"} or not isinstance(args["ticket_id"], str) or not 1 <= len(args["ticket_id"]) <= 32):
        raise ValueError("Invalid ticket reference")
    if name == "ticket_snapshot":
        t = get_ticket(args["ticket_id"])
        if not t: return {"error":"Ticket not found"}
        with connect() as c:
            loc = c.execute("SELECT display_name,location_type,verification_status,coordinate_source FROM campus_locations WHERE location_id=?", (t.location_id,)).fetchone() if t.location_id else None
        return {"ticket_id":t.ticket_id,"summary":t.summary,"category":t.category.value,"priority":t.priority.value,"service_team":t.department,"status":t.status.value,"location":t.location,"location_catalog":dict(loc) if loc else None,"created_at":t.created_at.isoformat(),"updated_at":t.updated_at.isoformat(),"resolution_note":t.resolution_note,"is_sample":t.is_sample}
    if name == "related_reports":
        t = get_ticket(args["ticket_id"])
        if not t: return {"error":"Ticket not found"}
        cand = [x for x in list_tickets() if x.ticket_id != t.ticket_id and x.status != Status.WITHDRAWN and not x.is_sample and ((t.location_id and x.location_id == t.location_id) or (t.location and x.location and t.location.casefold().strip() == x.location.casefold().strip()) or x.category == t.category)]
        cand.sort(key=lambda x:(x.location_id == t.location_id if t.location_id else False, x.category == t.category, x.created_at), reverse=True)
        return [{"ticket_id":x.ticket_id,"summary":x.summary,"category":x.category.value,"status":x.status.value,"priority":x.priority.value,"location":x.location} for x in cand[:20]]
    if name == "ticket_history":
        if not get_ticket(args["ticket_id"]): return {"error":"Ticket not found"}
        return [{"at":x["at"],"who":x["who"],"kind":x["kind"],"text":x["text"][:300]} for x in get_timeline(args["ticket_id"], actor=actor) if x["kind"] != "internal"][-20:]
    if name == "search_campus_locations":
        term = args.get("search_term", ""); typ = args.get("location_type")
        if not isinstance(term,str) or len(term)>100 or typ not in (None,"campus","building","facility","floor","department"): raise ValueError("Invalid catalog filter")
        with connect() as c:
            rows=c.execute("SELECT display_name,location_type,verification_status,coordinate_source,latitude,longitude,source_url FROM campus_locations WHERE display_name LIKE ? AND (? IS NULL OR location_type=?) ORDER BY display_name LIMIT 20",(f"%{term}%",typ,typ)).fetchall()
        return [dict(r) for r in rows]
    if name == "campus_issue_statistics":
        filters={k:args.get(k) for k in ("category","status","location","date_from","date_to") if args.get(k) is not None}
        if "category" in filters and filters["category"] not in {x.value for x in Category}: raise ValueError("Invalid category")
        if "status" in filters and filters["status"] not in {x.value for x in Status if x != Status.WITHDRAWN}: raise ValueError("Invalid status")
        for k in ("date_from","date_to"):
            if k in filters: date.fromisoformat(filters[k])
        if filters.get("date_from") and filters.get("date_to") and filters["date_from"]>filters["date_to"]: raise ValueError("Invalid date range")
        sql="SELECT COUNT(*) AS total FROM tickets WHERE status != 'Withdrawn' AND is_sample=0"; vals=[]
        for k,col in (("category","category"),("status","status"),("location","location"),("date_from","created_at"),("date_to","created_at")):
            if k in filters:
                sql += f" AND {col}{' >= ?' if k=='date_from' else ' <= ?' if k=='date_to' else ' = ?'}"; vals.append(filters[k] + ("T23:59:59" if k=="date_to" else "T00:00:00") if k in ("date_from","date_to") else filters[k])
        with connect() as c: n=c.execute(sql,vals).fetchone()[0]
        return {"count":n,"filters":filters,"exclusions":["withdrawn","sample"]}
    if name == "list_related_open_issues":
        loc=args.get("location"); cat=args.get("category")
        if loc is not None and (not isinstance(loc,str) or len(loc)>100): raise ValueError("Invalid location")
        if cat is not None and cat not in {x.value for x in Category}: raise ValueError("Invalid category")
        rows=[x for x in list_tickets() if x.status in {Status.OPEN,Status.IN_PROGRESS,Status.REOPENED} and not x.is_sample and (not cat or x.category.value==cat) and (not loc or (x.location and loc.casefold() in x.location.casefold()))]
        return [{"ticket_id":x.ticket_id,"summary":x.summary,"category":x.category.value,"status":x.status.value,"priority":x.priority.value,"location":x.location} for x in rows[:20]]


def _fallback(status="unavailable", text="Investigation AI is unavailable. Review the ticket and records directly."):
    return AgentResponse(answer=text, uncertainties=["No validated AI investigation response is available."], requires_human_review=True, status=status)


def investigate(ticket_id, actor, question=None, history=None, client=None):
    started=time.monotonic(); tool_count=0; settings=get_settings()
    try: _staff(actor)
    except Exception: return _fallback(text="Only signed-in staff can run an investigation.")
    ticket_id=(ticket_id or "").strip().upper(); question=(question or f"Investigate ticket {ticket_id}.").strip()
    if not ticket_id or len(ticket_id)>32 or not question or len(question)>2000: return _fallback(text="Enter a valid ticket reference and a question of at most 2,000 characters.")
    if not get_ticket(ticket_id): return _fallback(text="Ticket not found. Check the reference and try again.")
    if not settings.api_key and client is None: return _fallback(text="Investigation AI is not configured. The staff map and ticket records remain available.")
    log.info("investigation_started", extra={"actor_id": actor.id})
    try:
        if client is None:
            from ai_service import _make_client
            client=_make_client(settings)
        msgs=[{"role":"system","content":SYSTEM_PROMPT}]
        # Session history is context, never trusted instructions or replayable tool output.
        safe_history=[]
        for item in history or []:
            if isinstance(item, dict) and item.get("role") in {"user", "assistant"} and isinstance(item.get("content"), str):
                safe_history.append({"role":item["role"],"content":item["content"][:3000]})
        if settings.agent_max_history_messages:
            msgs.extend(safe_history[-settings.agent_max_history_messages:])
        msgs.append({"role":"user","content":f"Current ticket reference: {ticket_id}. Staff question: {question}"})
        for _ in range(settings.agent_max_turns):
            remaining=settings.agent_timeout_seconds-(time.monotonic()-started)
            if remaining <= 0: return _fallback("partial","Investigation reached its time limit before producing a validated answer.")
            res=client.chat.completions.create(model=settings.model,messages=msgs,tools=TOOLS,tool_choice="auto",temperature=0,timeout=remaining)
            msg=res.choices[0].message
            if not msg.tool_calls:
                raw=msg.content or "{}"
                if isinstance(raw,str): raw=json.loads(raw)
                out=AgentResponse.validate_output(raw)
                # Agent citations must refer to records actually returned during this run.
                known=set()
                for item in msgs:
                    if item.get("role")=="tool":
                        try:
                            value=json.loads(item["content"])
                            if isinstance(value,dict) and value.get("ticket_id"): known.add(value["ticket_id"])
                            if isinstance(value,list): known.update(x.get("ticket_id") for x in value if isinstance(x,dict) and x.get("ticket_id"))
                        except Exception: pass
                out.evidence=[x for x in out.evidence if x in known]
                out.related_tickets=[x for x in out.related_tickets if x in known]
                msgs.append({"role":"assistant","content":out.model_dump_json()})
                log.info("investigation_completed",extra={"tools":tool_count,"status":out.status,"duration_ms":int((time.monotonic()-started)*1000)})
                kept_history=[m for m in msgs if m.get("role") in {"user","assistant"} and isinstance(m.get("content"),str)]
                return out, kept_history[-settings.agent_max_history_messages:] if settings.agent_max_history_messages else []
            msgs.append(msg.model_dump(exclude_none=True))
            calls=msg.tool_calls
            if len(calls)>settings.agent_max_tool_calls_per_turn: return _fallback("partial","Investigation stopped at the per-turn tool limit.")
            if tool_count+len(calls)>settings.agent_max_tool_calls: return _fallback("partial","Investigation stopped at the total tool-call limit.")
            for call in calls:
                name=call.function.name
                log.info("investigation_tool_selected", extra={"tool": name if name in _ALLOWED else "unknown"})
                if name not in _ALLOWED: result={"error":"Unknown tool"}
                else:
                    try: result=execute_tool(name,json.loads(call.function.arguments or "{}"),actor)
                    except Exception as exc: result={"error":f"Tool request rejected ({type(exc).__name__})"}
                tool_count+=1
                msgs.append({"role":"tool","tool_call_id":call.id,"content":json.dumps(result,ensure_ascii=False,default=str)})
        return _fallback("partial","Investigation reached the model-turn limit before producing a validated answer.")
    except (ValidationError,ValueError,TypeError,json.JSONDecodeError):
        log.warning("investigation_invalid_output",extra={"tools":tool_count})
        return _fallback("partial","The investigation response could not be validated. Review the records directly.")
    except Exception as exc:
        log.warning("investigation_provider_error",extra={"category":type(exc).__name__,"tools":tool_count})
        return _fallback(text="The investigation service is temporarily unavailable. Review the ticket and related records directly.")
