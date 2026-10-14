"""Logic tests with a fake in-memory chain (no real nodes needed)."""
import json, os, sys, tempfile
import ledger_worker as lw

class FakeChain:
    def __init__(self, fail_submit=False, hide_from_node3=False):
        self.store, self.submits = {}, 0
        self.fail_submit, self.hide3 = fail_submit, hide_from_node3
    def find_all(self, hid, eid, h):
        ref = self.store.get((hid, eid, h))
        return {"node1": ref, "node2": ref, "node3": None if self.hide3 else ref}
    def submit(self, hid, eid, h):
        if self.fail_submit: raise lw.TransientError("node down")
        self.submits += 1
        self.store[(hid, eid, h)] = "TXHASH" + eid[:8]
    def wait_ref(self, hid, eid, h): return self.store.get((hid, eid, h))
    def wait_all(self, hid, eid, h):
        f = self.find_all(hid, eid, h); v = set(f.values())
        return v.pop() if None not in v and len(v) == 1 else None

def fresh():
    d = tempfile.mkdtemp(); p = os.path.join(d, "ev.json")
    json.dump(lw.sample_rows(), open(p, "w")); return lw.MockBridge(p), p
def status(p): return {r["event_id"][:8]: r for r in json.load(open(p))}

fails = 0
def check(name, ok):
    global fails; print(("PASS  " if ok else "FAIL  ") + name); fails += 0 if ok else 1
q = lambda *_a, **_k: None

# 1. normal run: valid -> CONFIRMED, tampered -> DEAD_LETTER (no submit for it)
b, p = fresh(); c = FakeChain(); lw.run(b, c, log=q); s = status(p)
check("valid event CONFIRMED", s["8aa5b9c2"]["status"] == "CONFIRMED")
check("confirmation method recorded", s["8aa5b9c2"].get("confirmation_method") == "MULTINODE_CONSISTENCY")
check("ledger_reference saved", s["8aa5b9c2"]["ledger_reference"].startswith("TXHASH"))
check("tampered event DEAD_LETTER", s["11111111"]["status"] == "DEAD_LETTER")
check("tampered event never submitted", c.submits == 1)
check("tampered event keeps last_error", "mismatch" in s["11111111"]["last_error"])

# 2. recovery: anchor already on chain, event back to PENDING -> no second submit
rows = json.load(open(p)); rows[0]["status"] = "PENDING"; json.dump(rows, open(p, "w"))
lw.run(b, c, log=q)
check("recovery does NOT resubmit", c.submits == 1)
check("recovery ends CONFIRMED", status(p)["8aa5b9c2"]["status"] == "CONFIRMED")

# 3. node down -> RETRY, then success next round
b, p = fresh(); c = FakeChain(fail_submit=True); lw.run(b, c, log=q)
check("node down -> RETRY", status(p)["8aa5b9c2"]["status"] == "RETRY")
c.fail_submit = False; lw.run(b, c, log=q)
check("retry succeeds later", status(p)["8aa5b9c2"]["status"] == "CONFIRMED")

# 4. one node cannot see the anchor -> not confirmed, no duplicate submit afterwards
b, p = fresh(); c = FakeChain(hide_from_node3=True); lw.run(b, c, log=q)
s = status(p)["8aa5b9c2"]
check("node3 missing -> not CONFIRMED", s["status"] == "RETRY")
check("SUBMITTED reference was still stored", s.get("ledger_reference", "").startswith("TXHASH"))
lw.run(b, c, log=q)
check("re-check does not resubmit", c.submits == 1)

# 5. retry limit -> DEAD_LETTER
b, p = fresh(); c = FakeChain(fail_submit=True)
for _ in range(lw.MAX_RETRIES + 1):
    lw.run(b, c, log=q)
check("retry limit -> DEAD_LETTER", status(p)["8aa5b9c2"]["status"] == "DEAD_LETTER")

print("\nALL PASSED" if not fails else f"\n{fails} FAILED"); sys.exit(1 if fails else 0)
