"""Runs the REAL openai client against a local fake OpenAI-compatible server (no internet, no key)."""
import json, threading, time
from http.server import BaseHTTPRequestHandler, HTTPServer
import pytest
from ai_service import analyze_complaint
from config import Settings

MODE = {"m": "ok"}
GOOD = {"summary": "Outage in Hostel Block B", "category": "Electricity", "priority": "High", "rationale": "Many affected."}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        m = MODE["m"]
        if m == "slow": time.sleep(2)
        code = {"401": 401, "429": 429, "500": 500}.get(m, 200)
        content = "this is not json" if m == "badjson" else json.dumps(GOOD)
        body = json.dumps({"id": "x", "object": "chat.completion", "created": 0, "model": "m",
                           "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": content}}]}
                          if code == 200 else {"error": {"message": "nope"}})
        self.send_response(code); self.send_header("Content-Type", "application/json"); self.end_headers()
        self.wfile.write(body.encode())


@pytest.fixture(scope="module")
def server():
    s = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{s.server_port}/v1"
    s.shutdown()


def cfg(url, timeout=20):
    return Settings(api_key="test-key", base_url=url, model="m", db_path="x.db", dup_threshold=70, ai_timeout=timeout)


@pytest.mark.parametrize("mode,expected", [("ok", "llm"), ("badjson", "fallback"), ("401", "fallback"), ("429", "fallback"), ("500", "fallback")])
def test_real_client_paths(server, mode, expected):
    MODE["m"] = mode
    out = analyze_complaint("No electricity in Hostel Block B since morning", settings=cfg(server))
    assert out.mode == expected
    if expected == "fallback": assert out.result.review_required and out.warning


def test_real_client_timeout_falls_back(server):
    MODE["m"] = "slow"
    assert analyze_complaint("No electricity in Hostel Block B", settings=cfg(server, timeout=0.5)).mode == "fallback"
