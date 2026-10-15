"""
test_http_bridge.py - tests HttpBridge against a fake IOTA_API server (local only).
Also runs the Worker end to end (fake chain, real HTTP) to check the status flow.
"""
import json, sys, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import ledger_worker as lw
from http_bridge import HttpBridge, BridgeAuthError

TOKEN = "test-token-123"

class State:
    def __init__(self):
        self.rows = {r["event_id"]: dict(r) for r in lw.sample_rows()}
        self.fail_confirm = False
        self.conflict_submitted = False
        self.malformed = False
        self.last_claim = None

def make_server(state):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def _send(self, code, obj):
            b = json.dumps(obj).encode()
            self.send_response(code); self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
        def _body(self):
            n = int(self.headers.get("Content-Length") or 0)
            return json.loads(self.rfile.read(n) or b"{}")
        def _auth(self):
            if self.headers.get("Authorization") != f"Bearer {TOKEN}":
                self._send(401, {"error": "bad token"}); return False
            return True
        def do_GET(self):
            if not self._auth(): return
            if self.path == "/ledger/health": self._send(200, {"ok": True})
            else: self._send(404, {})
        def do_POST(self):
            if not self._auth(): return
            b = self._body(); p = self.path
            if p == "/ledger/claim":
                state.last_claim = b
                if state.malformed:
                    return self._send(200, {"events": [{"event_id": "x"}]})
                out = []
                for r in state.rows.values():
                    if r["status"] in ("PENDING", "RETRY") and len(out) < b["limit"]:
                        r["status"] = "PROCESSING"
                        out.append({k: r[k] for k in ("event_id", "payload", "payload_hash", "retry_count")})
                return self._send(200, {"events": out})
            parts = p.strip("/").split("/")
            if len(parts) == 3 and parts[0] == "ledger" and parts[1] in state.rows:
                r, act = state.rows[parts[1]], parts[2]
                if act == "submitted":
                    if state.conflict_submitted: return self._send(409, {})
                    r["status"], r["ledger_reference"] = "SUBMITTED", b["ledger_reference"]
                elif act == "confirm":
                    if state.fail_confirm: return self._send(500, {})
                    r["status"], r["ledger_reference"] = "CONFIRMED", b["ledger_reference"]
                    r["confirmation_method"] = b["confirmation_method"]
                elif act == "fail":
                    r["retry_count"] += 1; r["last_error"] = b["error"]
                    r["status"] = "RETRY" if b["retryable"] and r["retry_count"] < 5 else "DEAD_LETTER"
                else: return self._send(404, {})
                return self._send(200, {"ok": True})
            self._send(404, {})
    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv

class FakeChain:
    def __init__(self): self.store, self.submits = {}, 0
    def find_all(self, h, e, x):
        r = self.store.get((h, e, x)); return {"n1": r, "n2": r, "n3": r}
    def submit(self, h, e, x): self.submits += 1; self.store[(h, e, x)] = "TX" + e[:8]
    def wait_ref(self, h, e, x): return self.store.get((h, e, x))
    def wait_all(self, h, e, x): return self.store.get((h, e, x))

fails = 0
def check(name, ok):
    global fails; print(("PASS  " if ok else "FAIL  ") + name); fails += 0 if ok else 1
q = lambda *_a, **_k: None
GOOD, BAD = "8aa5b9c2-5c4b-4f08-9cb5-4d163c0119a1", "11111111-2222-3333-4444-555555555555"

# 1. normal flow over real HTTP
st = State(); srv = make_server(st); url = f"http://127.0.0.1:{srv.server_port}"
br = HttpBridge(url, TOKEN, worker_id="w-test", lease_seconds=77, log=q); ch = FakeChain()
check("health works", br.health() == {"ok": True})
lw.run(br, ch, log=q)
check("claim sent worker_id/limit/lease", st.last_claim == {"worker_id": "w-test", "limit": 5, "lease_seconds": 77})
check("valid event CONFIRMED", st.rows[GOOD]["status"] == "CONFIRMED")
check("confirmation_method stored", st.rows[GOOD].get("confirmation_method") == "MULTINODE_CONSISTENCY")
check("tampered event DEAD_LETTER", st.rows[BAD]["status"] == "DEAD_LETTER")
check("tampered event not submitted to chain", ch.submits == 1)

# 2. wrong token is fatal, not silently ignored
bad = HttpBridge(url, "wrong", log=q)
try: bad.claim(); check("wrong token raises BridgeAuthError", False)
except BridgeAuthError: check("wrong token raises BridgeAuthError", True)

# 3. API down: claim returns [] and does not crash
srv.shutdown(); srv.server_close()
check("API down -> claim returns []", HttpBridge(url, TOKEN, timeout=2, log=q).claim() == [])

# 4. confirm fails (API error) -> event not CONFIRMED, later recovered WITHOUT resubmitting
st = State(); st.fail_confirm = True; srv = make_server(st)
url = f"http://127.0.0.1:{srv.server_port}"; br = HttpBridge(url, TOKEN, log=q); ch = FakeChain()
lw.run(br, ch, log=q)
check("confirm 500 -> not CONFIRMED on server", st.rows[GOOD]["status"] == "RETRY")
st.fail_confirm = False; lw.run(br, ch, log=q)
check("recovered to CONFIRMED later", st.rows[GOOD]["status"] == "CONFIRMED")
check("recovery did not resubmit", ch.submits == 1)
srv.shutdown(); srv.server_close()

# 5. 409 on submitted (someone else took the event) -> retry path, no crash
st = State(); st.conflict_submitted = True; srv = make_server(st)
url = f"http://127.0.0.1:{srv.server_port}"; br = HttpBridge(url, TOKEN, log=q); ch = FakeChain()
lw.run(br, ch, log=q)
check("409 on submitted -> RETRY, no crash", st.rows[GOOD]["status"] == "RETRY")
srv.shutdown(); srv.server_close()

# 6. malformed claim items are dropped
st = State(); st.malformed = True; srv = make_server(st)
url = f"http://127.0.0.1:{srv.server_port}"
check("malformed event dropped", HttpBridge(url, TOKEN, log=q).claim() == [])
srv.shutdown(); srv.server_close()

print("\nALL PASSED" if not fails else f"\n{fails} FAILED"); sys.exit(1 if fails else 0)
