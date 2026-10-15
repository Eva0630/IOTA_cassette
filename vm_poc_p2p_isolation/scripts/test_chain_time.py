"""test_chain_time.py - checks time decoding and chronological ordering (no nodes needed)."""
import os, random, sys, time
os.environ["AUDIT_MASTER_KEY"] = "ab" * 32
import chain_time as ct
import audit_isolation_test as iso
from audit_chain_utils import household_to_address, action_to_tag, encrypt_message, ascii_to_trytes, pad_trytes
from send_audit_event import int_to_trytes

def make_tx(hid, text, ts, att_ms):
    """Build a transaction exactly like send_audit_event.py does, plus the node's attach time."""
    msg = pad_trytes(ascii_to_trytes(encrypt_message(text, hid)), 2187)
    tag = action_to_tag("unlock_door")
    return (msg + household_to_address(hid) + int_to_trytes(0, 27) + tag + int_to_trytes(ts, 9)
            + int_to_trytes(0, 9) + int_to_trytes(0, 9) + "9" * 81 + "9" * 81 + "9" * 81
            + tag + int_to_trytes(att_ms, 9) + "9" * 9 + "9" * 9 + "9" * 27)

fails = 0
def check(name, ok):
    global fails; print(("PASS  " if ok else "FAIL  ") + name); fails += 0 if ok else 1

# 1. field offsets match the transaction layout
check("layout is 2673 trytes", len(make_tx("A", "x", 1, 1)) == 2673)

# 2. decode is the exact inverse of the encoder used on chain
now = int(time.time())
for v in (0, 1, 26, 27, 1790000000, now, 1790000000123):
    tx = make_tx("A", "x", v, v)
    check(f"round trip {v}", ct.tx_timestamp(tx) == v and ct.tx_attachment_ms(tx) == v)

# 3. ordering: scrambled input -> oldest first
base = 1790000000
events = [("e1", base), ("e2", base + 60), ("e3", base + 3600), ("e4", base + 86400)]
txs = [make_tx("A", '{"n":"%s"}' % n, ts, ts * 1000) for n, ts in events]
scrambled = [txs[2], txs[0], txs[3], txs[1]]
out = ct.records_in_order(scrambled, "A")
check("sorted oldest first", [o.split('"n":"')[1][:2] for o in out] == ["e1", "e2", "e3", "e4"])
check("time prefix is shown", out[0].startswith("[") and "] " in out[0])

# 4. same second -> attach time breaks the tie
a = make_tx("A", '{"n":"first"}', base, base * 1000 + 5)
b = make_tx("A", '{"n":"second"}', base, base * 1000 + 900)
out = ct.records_in_order([b, a], "A")
check("same second: attach time decides", "first" in out[0] and "second" in out[1])

# 5. every node returns the same order no matter how it lists the transactions
random.seed(7)
orders = set()
for _ in range(20):
    s = txs[:]; random.shuffle(s)
    orders.add(tuple(ct.records_in_order(s, "A")))
check("output identical for any input order", len(orders) == 1)

# 6. end to end through query_audit_log with fake nodes in different orders
class Resp:
    def __init__(self, d): self.d = d
    def json(self): return self.d
def fake_post_factory(order):
    hashes = ["H%d" % i for i in range(len(txs))]
    mapping = dict(zip(hashes, txs))
    seq = [hashes[i] for i in order]
    def fake_post(url, json=None, headers=None):
        if json["command"] == "findTransactions": return Resp({"hashes": seq})
        return Resp({"trytes": [mapping[h] for h in json["hashes"]]})
    return fake_post
results = []
for order in ([2, 0, 3, 1], [3, 2, 1, 0], [0, 1, 2, 3]):
    iso.requests.post = fake_post_factory(order)
    r = iso.query_audit_log("user_A_resident", "A")
    results.append(r["records"])
check("query returns oldest first", [x.split('"n":"')[1][:2] for x in results[0]] == ["e1", "e2", "e3", "e4"])
check("query result same for every node order", results[0] == results[1] == results[2])
check("consensus flag still works", r["multi_node_consensus"] is True)

# 7. garbage input does not crash
check("short/garbage transaction does not crash", len(ct.records_in_order(["9" * 10, txs[0]], "A")) == 2)

print("\nALL PASSED" if not fails else f"\n{fails} FAILED"); sys.exit(1 if fails else 0)
