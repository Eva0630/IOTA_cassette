"""
ledger_worker.py
Ledger Worker: anchors PENDING ledger events on the private Tangle.

Flow per event:
  1. claim from the bridge (PENDING/RETRY -> PROCESSING)
  2. verify: canonical-JSON SHA-256 == payload_hash, event_id matches
  3. look on the chain FIRST (crash recovery: never blindly resubmit)
  4. if not found: submit an anchor (event_id + payload_hash) via send_audit_event
  5. report SUBMITTED with the tx hash as ledger_reference
  6. wait until ALL 3 nodes return the same anchor tx (else RETRY)
  7. wait up to milestone_wait seconds for a Compass milestone to confirm it
     (getInclusionStates against the latest solid milestone, see iota_bundle.py):
       confirmed     -> report CONFIRMED, confirmation_method = MILESTONE
       not in time   -> report CONFIRMED, confirmation_method = MULTINODE_CONSISTENCY
                        (the old behaviour; e.g. anchors written before the bundle-hash
                        fix can never be milestone-confirmed)
  8. on error: fail(retryable=True/False)

The anchor is a normal encrypted audit record (action "ledger_anchor") under the
household address of the event's family_id, so UC5.3 isolation applies to it.

Usage:
  python3 ledger_worker.py --init-mock          create sample events file
  python3 ledger_worker.py --mock --once        process them once
"""
import argparse
import hashlib
import json
import os
import sys
import time

NODES = {
    "node1": "http://localhost:14265",
    "node2": "http://localhost:14266",
    "node3": "http://localhost:14267",
}
HEADERS = {"Content-Type": "application/json", "X-IOTA-API-Version": "1"}
MAX_RETRIES = 5
CONFIRM_METHOD = "MULTINODE_CONSISTENCY"     # fallback: all 3 nodes return the same anchor
CONFIRM_MILESTONE = "MILESTONE"              # a Compass milestone references the anchor
MILESTONE_WAIT = int(os.environ.get("LEDGER_MILESTONE_WAIT", "120"))   # seconds; TICK_RATE is 30 s


class PermanentError(Exception):
    """Do not retry (bad data)."""


class TransientError(Exception):
    """Safe to retry later."""


# ---------------- hashing (same rule as the API's ledger_event_service) ----------------

def canonical_json(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def verify_event(row: dict) -> dict:
    raw = row["payload"]
    event = json.loads(raw) if isinstance(raw, (str, bytes, bytearray)) else raw
    if not isinstance(event, dict):
        raise PermanentError("payload is not a JSON object")
    if sha256_hex(canonical_json(event)) != row["payload_hash"]:
        raise PermanentError("payload_hash mismatch")
    if event.get("event_id") != row["event_id"]:
        raise PermanentError("event_id mismatch")
    if event.get("family_id") is None:
        raise PermanentError("family_id missing")
    return event


# ---------------- chain access (real) ----------------

class IotaChain:
    def __init__(self, nodes=NODES, node1_wait=15, all_nodes_wait=90, milestone_wait=None):
        self.nodes = nodes
        self.node1_wait = node1_wait
        self.all_nodes_wait = all_nodes_wait
        self.milestone_wait = MILESTONE_WAIT if milestone_wait is None else milestone_wait

    def _post(self, url, body):
        import requests
        return requests.post(url, json=body, headers=HEADERS, timeout=15).json()

    def find_on_node(self, url, household_id, event_id, payload_hash):
        """Return the tx hash of this event's anchor on one node, or None.
        Smallest hash wins so every node picks the same one even if duplicated."""
        from audit_chain_utils import household_to_address, trytes_to_ascii
        from crypto_utils import read_record
        try:
            addr = household_to_address(household_id)
            hashes = self._post(url, {"command": "findTransactions", "addresses": [addr]}).get("hashes", [])
            if not hashes:
                return None
            trytes = self._post(url, {"command": "getTrytes", "hashes": hashes}).get("trytes", [])
        except Exception:
            return None
        want = f"event_id:{event_id};hash:{payload_hash}"
        matches = []
        for h, t in zip(hashes, trytes):
            try:
                rec = json.loads(read_record(trytes_to_ascii(t[:2187]), household_id))
            except Exception:
                continue
            if rec.get("action") == "ledger_anchor" and rec.get("result") == want:
                matches.append(h)
        return sorted(matches)[0] if matches else None

    def find_all(self, household_id, event_id, payload_hash):
        return {n: self.find_on_node(u, household_id, event_id, payload_hash)
                for n, u in self.nodes.items()}

    def submit(self, household_id, event_id, payload_hash):
        from send_audit_event import send_audit_event
        try:
            r = send_audit_event(household_id, "ledger_anchor", "LEDGER_WORKER",
                                 f"event_id:{event_id};hash:{payload_hash}")
        except Exception as e:
            raise TransientError(f"submit failed: {e}")
        if r is None:
            raise TransientError("submit failed (node rejected the transaction)")

    def wait_ref(self, household_id, event_id, payload_hash):
        first = list(self.nodes.values())[0]
        end = time.time() + self.node1_wait
        while time.time() < end:
            ref = self.find_on_node(first, household_id, event_id, payload_hash)
            if ref:
                return ref
            time.sleep(2)
        return None

    def wait_all(self, household_id, event_id, payload_hash):
        """Return the tx hash once every node agrees, else None."""
        end = time.time() + self.all_nodes_wait
        while True:
            found = self.find_all(household_id, event_id, payload_hash)
            vals = set(found.values())
            if None not in vals and len(vals) == 1:
                return vals.pop()
            if time.time() >= end:
                return None
            time.sleep(3)

    def is_milestone_confirmed(self, tx_hash):
        """True if node1 says a milestone confirms tx_hash (getInclusionStates)."""
        from iota_bundle import inclusion_states
        first = list(self.nodes.values())[0]
        return inclusion_states(first, [tx_hash])[0]

    def wait_milestone(self, tx_hash):
        """Poll for milestone confirmation up to milestone_wait seconds. Never raises."""
        end = time.time() + self.milestone_wait
        while True:
            try:
                if self.is_milestone_confirmed(tx_hash):
                    return True
            except Exception:
                pass
            if time.time() >= end:
                return False
            time.sleep(5)


# ---------------- bridge (mock now; HTTP once the API endpoints exist) ----------------

class MockBridge:
    """File-backed stand-in for the IOTA_API claim/submitted/confirm/fail endpoints."""

    def __init__(self, path):
        self.path = path

    def _load(self):
        with open(self.path, encoding="utf-8") as f:
            return json.load(f)

    def _save(self, rows):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=2)

    def _get(self, rows, eid):
        return next(r for r in rows if r["event_id"] == eid)

    def claim(self, limit=5):
        rows = self._load()
        out = [r for r in rows if r["status"] in ("PENDING", "RETRY")][:limit]
        for r in out:
            r["status"] = "PROCESSING"
        self._save(rows)
        return [dict(r) for r in out]

    def submitted(self, eid, ref):
        rows = self._load(); r = self._get(rows, eid)
        r["status"], r["ledger_reference"] = "SUBMITTED", ref
        self._save(rows)

    def confirm(self, eid, ref, method):
        rows = self._load(); r = self._get(rows, eid)
        r["status"], r["ledger_reference"], r["confirmation_method"] = "CONFIRMED", ref, method
        self._save(rows)

    def fail(self, eid, error, retryable):
        rows = self._load(); r = self._get(rows, eid)
        r["retry_count"] = r.get("retry_count", 0) + 1
        r["last_error"] = error
        r["status"] = "RETRY" if retryable and r["retry_count"] < MAX_RETRIES else "DEAD_LETTER"
        self._save(rows)


# ---------------- core ----------------

def process_event(row, bridge, chain, log=print):
    eid = row["event_id"]
    try:
        event = verify_event(row)
        hid = str(event["family_id"])
        h = row["payload_hash"]

        found = chain.find_all(hid, eid, h)
        ref = next((v for v in found.values() if v), None)
        if ref:
            log(f"  [{eid[:8]}] anchor already on chain -> skip submit (recovery)")
        else:
            if row.get("recovery_required") or row.get("ledger_reference"):
                raise TransientError("recovery: anchor not visible; refusing automatic resubmission, inspect chain before manual reset")
            log(f"  [{eid[:8]}] submitting anchor for family {hid}")
            chain.submit(hid, eid, h)
            ref = chain.wait_ref(hid, eid, h)
            if ref is None:
                raise TransientError("submitted but not visible yet; will re-check, not resubmit")
        bridge.submitted(eid, ref)

        agreed = chain.wait_all(hid, eid, h)
        if agreed is None:
            raise TransientError("anchor not yet identical on all 3 nodes")
        method = CONFIRM_METHOD
        wait_milestone = getattr(chain, "wait_milestone", None)   # fake chains in tests may lack it
        if wait_milestone is not None:
            if wait_milestone(agreed):
                method = CONFIRM_MILESTONE
            else:
                log(f"  [{eid[:8]}] no milestone confirmation in time -> falling back to {CONFIRM_METHOD}")
        bridge.confirm(eid, agreed, method)
        log(f"  [{eid[:8]}] CONFIRMED ({method})  ref={agreed[:16]}...")
        return "CONFIRMED"
    except PermanentError as e:
        bridge.fail(eid, str(e), False)
        log(f"  [{eid[:8]}] FAILED (permanent): {e}")
        return "DEAD_LETTER"
    except TransientError as e:
        bridge.fail(eid, str(e), True)
        log(f"  [{eid[:8]}] FAILED (will retry): {e}")
        return "RETRY"


def run(bridge, chain, once=True, interval=10, log=print):
    while True:
        rows = bridge.claim(5)
        log(f"claimed {len(rows)} event(s)")
        for row in rows:
            process_event(row, bridge, chain, log)
        if once:
            return
        time.sleep(interval)


# ---------------- sample data for the mock bridge ----------------

def sample_rows():
    ev = {
        "schema_version": "1.0", "uc_id": "UC3.4",
        "event_id": "8aa5b9c2-5c4b-4f08-9cb5-4d163c0119a1",
        "event_type": "GUEST_TOKEN_ISSUED", "family_id": 12, "gateway_id": "GW_001",
        "source": "SERVER", "timestamp": "2026-09-30T13:30:00Z",
        "actor": {"actor_type": "USER", "actor_role": "ADMIN",
                  "actor_id_hash": "sha256:f51739fd6372274f543ab95b3aebfa03c824f976392bf40bb8cdca23b164fc22"},
        "payload": {
            "authorization_id": "QR_8cd4061785d54891b7b77b0c2bc39401",
            "credential_kind": "GUEST_ACCOUNT_QR",
            "guest_user_id_hash": "sha256:22149b2f0c4cbfffff279d85f87502035d2ab8a3d06d676d17d7cbdcb6a6dde0",
            "authorization_scope": {"scope_type": "FAMILY", "family_id": 12, "role": "GUEST",
                                    "policy_enforced_by": "GATEWAY"},
            "validity": {"valid_from": "2026-09-30T13:30:00Z", "expires_at": "2026-09-30T14:30:00Z"},
            "usage_limit": {"max_uses": 3}, "authorization_status": "ACTIVE"}}
    good = {"event_id": ev["event_id"], "payload": ev,
            "payload_hash": sha256_hex(canonical_json(ev)), "status": "PENDING", "retry_count": 0}
    bad_ev = json.loads(json.dumps(ev))
    bad_ev["event_id"] = "11111111-2222-3333-4444-555555555555"
    bad = {"event_id": bad_ev["event_id"], "payload": bad_ev,
           "payload_hash": sha256_hex(canonical_json(bad_ev)), "status": "PENDING", "retry_count": 0}
    bad["payload"]["payload"]["usage_limit"]["max_uses"] = 999   # changed AFTER hashing
    return [good, bad]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mock", action="store_true", help="use the file-backed mock bridge")
    ap.add_argument("--init-mock", action="store_true", help="(re)create the sample events file")
    ap.add_argument("--mock-file", default="mock_ledger_events.json")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--interval", type=int, default=10)
    a = ap.parse_args()

    if a.init_mock:
        with open(a.mock_file, "w", encoding="utf-8") as f:
            json.dump(sample_rows(), f, ensure_ascii=False, indent=2)
        print(f"wrote {a.mock_file} (1 valid event + 1 tampered event)")
        sys.exit(0)
    if not a.mock:
        print("Only --mock is available until the IOTA_API claim/confirm/fail endpoints exist.")
        sys.exit(2)
    if not os.environ.get("AUDIT_MASTER_KEY"):
        print("AUDIT_MASTER_KEY is not set. Run: export AUDIT_MASTER_KEY=$(cat ~/.audit_master_key)")
        sys.exit(2)
    run(MockBridge(a.mock_file), IotaChain(), once=a.once, interval=a.interval)
