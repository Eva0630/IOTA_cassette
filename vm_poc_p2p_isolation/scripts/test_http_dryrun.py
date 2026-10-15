"""test_http_dryrun.py - dry-run mode and --limit, against a fake IOTA_API (local only)."""
import copy, json, sys, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import ledger_worker as lw
from http_bridge import HttpBridge, dry_run

TOKEN = "t"
base = lw.sample_rows()[0]["payload"]            # the valid sample event
def row(event, h=None, as_string=False, eid=None):
    return {"event_id": eid or event["event_id"],
            "payload": json.dumps(event) if as_string else event,
            "payload_hash": h or lw.sha256_hex(lw.canonical_json(event)),
            "status": "PENDING", "retry_count": 0}

good = row(base)
tampered = lw.sample_rows()[1]
zh = copy.deepcopy(base); zh["event_id"] = "22222222-0000-0000-0000-000000000002"; zh["payload"]["note"] = "訪客開門"
zh_row = row(zh, h=lw.sha256_hex(json.dumps(zh, ensure_ascii=True, sort_keys=True, separators=(",", ":"))))
pf = copy.deepcopy(base); pf["event_id"] = "33333333-0000-0000-0000-000000000003"
pf_row = row(pf, h="sha256:" + lw.sha256_hex(lw.canonical_json(pf)))
st = copy.deepcopy(base); st["event_id"] = "44444444-0000-0000-0000-000000000004"
str_row = row(st, as_string=True)

class S:
    def __init__(self, rows): self.rows = rows; self.calls = []; self.last = None

def serve(state):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def do_POST(self):
            n = int(self.headers.get("Content-Length") or 0); b = json.loads(self.rfile.read(n) or b"{}")
            state.calls.append(self.path)
            if self.path == "/ledger/claim":
                state.last = b
                ev = [dict(r) for r in state.rows][: b["limit"]]
                out = json.dumps({"events": ev}).encode()
            else:
                out = b"{}"
            self.send_response(200); self.send_header("Content-Length", str(len(out))); self.end_headers(); self.wfile.write(out)
    srv = HTTPServer(("127.0.0.1", 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv

fails = 0
def check(name, ok):
    global fails; print(("PASS  " if ok else "FAIL  ") + name); fails += 0 if ok else 1

state = S([good, tampered, zh_row, pf_row, str_row]); srv = serve(state)
url = f"http://127.0.0.1:{srv.server_port}"
lines = []
br = HttpBridge(url, TOKEN, lease_seconds=15, max_claim=10, log=lines.append)
ok = dry_run(br, 10, log=lines.append)
text = "\n".join(lines)
print(text); print()

check("claim used the short lease", state.last["lease_seconds"] == 15)
check("dry run touched ONLY /ledger/claim", set(state.calls) == {"/ledger/claim"})
check("returns False when something failed", ok is False)
check("valid event reported OK", "✅ 8aa5b9c2" in text)
check("payload sent as a JSON string is accepted", "✅ 44444444" in text)
check("tampered event reported with expected/computed", "❌ 11111111" in text and "computed :" in text)
check("tampered event: no serialization explains it", text.split("❌ 11111111")[1].split("❌")[0].count("none") == 1)
check("non-ASCII mismatch is diagnosed as ensure_ascii", "ensure_ascii=True" in text.split("❌ 22222222")[1])
check("sha256: prefix is diagnosed", "'sha256:' prefix" in text.split("❌ 33333333")[1])
check("prefix case does not wrongly blame ensure_ascii",
      "ensure_ascii" not in text.split("❌ 33333333")[1].split("✅")[0])
check("summary line is correct", "summary: 2/5 verified" in text)

# --limit
state2 = S([good, tampered, zh_row]); srv2 = serve(state2)
br2 = HttpBridge(f"http://127.0.0.1:{srv2.server_port}", TOKEN, max_claim=1, log=lambda *_: None)
rows = br2.claim(5)
check("--limit 1 asks the API for 1 event", state2.last["limit"] == 1 and len(rows) == 1)

# nothing to do
state3 = S([]); srv3 = serve(state3); l3 = []
ok3 = dry_run(HttpBridge(f"http://127.0.0.1:{srv3.server_port}", TOKEN, log=l3.append), 5, log=l3.append)
check("empty queue is not an error", ok3 is True and "claimed 0" in l3[0])

print("\nALL PASSED" if not fails else f"\n{fails} FAILED"); sys.exit(1 if fails else 0)
