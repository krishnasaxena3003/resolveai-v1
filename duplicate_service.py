"""Duplicate candidates. A score is a hint for staff review, never proof of the same incident.

Method: compare the PROBLEM wording (location words removed, synonyms and simple stems folded)
with a Dice overlap, then penalise reports that clearly come from different places.
Tuned on evaluation/duplicate_pairs.json (see eval_duplicates.py)."""
import re
from rapidfuzz import fuzz
from schemas import DuplicateCandidate, Status, TicketRecord

DEFAULT_THRESHOLD = 45.0
STOP = set("the a an in at of is are was to and on for it near from has have been since this that with by my our please".split())
SYN = {"wifi": "internet", "network": "internet", "net": "internet", "power": "electricity", "electric": "electricity", "electrical": "electricity",
       "current": "electricity", "cut": "outage", "outage": "outage", "off": "outage", "washroom": "toilet", "bathroom": "toilet", "restroom": "toilet",
       "wont": "not", "doesnt": "not", "cant": "not", "stopped": "not", "bad": "not"}


def _stem(w: str) -> str:
    for suf in ("ing", "ed", "es", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            w = w[: -len(suf)]
            break
    return SYN.get(w, w)


def tokens(text: str) -> list[str]:
    t = re.sub(r"wi[\s-]?fi", "wifi", (text or "").lower())
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    return [_stem(w) for w in t.split() if w not in STOP]


def normalize(text: str) -> str:
    return " ".join(tokens(text))


def _ident(toks: set[str]) -> set[str]:
    return {t for t in toks if t.isdigit() or len(t) == 1}  # block letters, room numbers


def different_place(loc_a: str | None, loc_b: str | None) -> bool:
    a, b = set(tokens(loc_a or "")), set(tokens(loc_b or ""))
    if not a or not b:
        return False  # unknown location: no evidence either way
    ia, ib = _ident(a), _ident(b)
    if ia and ib and ia != ib:
        return True
    return len(a & b) / len(a | b) < 0.5


def similarity(desc_a: str, loc_a: str | None, desc_b: str, loc_b: str | None) -> float:
    drop = set(tokens(loc_a or "")) | set(tokens(loc_b or ""))
    a = {t for t in tokens(desc_a) if t not in drop}
    b = {t for t in tokens(desc_b) if t not in drop}
    if not a or not b:
        return 0.0
    score = 200.0 * len(a & b) / (len(a) + len(b))
    if different_place(loc_a, loc_b):
        score *= 0.4  # same wording from a clearly different place is rarely the same incident
    return max(0.0, round(score, 1))


def legacy_similarity(desc_a, loc_a, desc_b, loc_b) -> float:
    """The first version (RapidFuzz token_set_ratio). Kept only as an evaluation baseline."""
    norm = lambda s: " ".join(w for w in re.sub(r"[^a-z0-9\s]", " ", (s or "").lower()).split() if w not in STOP)
    s = fuzz.token_set_ratio(norm(desc_a), norm(desc_b))
    if loc_a and loc_b and fuzz.token_set_ratio(norm(loc_a), norm(loc_b)) < 60:
        s -= 15
    return max(0.0, round(s, 1))


def find_candidates(description, location, existing: list[TicketRecord], threshold: float = DEFAULT_THRESHOLD, limit: int = 3):
    out = []
    for t in existing:
        if t.status in (Status.RESOLVED, Status.WITHDRAWN):
            continue
        s = similarity(description, location, t.description, t.location)
        if s >= threshold:
            drop = set(tokens(location or "")) | set(tokens(t.location or ""))
            shared = sorted((set(tokens(description)) & set(tokens(t.description))) - drop)
            note = "Same problem wording" + (", different place" if different_place(location, t.location) else ", same or unknown place")
            out.append(DuplicateCandidate(ticket_id=t.ticket_id, summary=t.summary, status=t.status, score=s,
                                          evidence=f"{note}. Shared terms: {', '.join(shared) or 'none'}"))
    return sorted(out, key=lambda c: -c.score)[:limit]
