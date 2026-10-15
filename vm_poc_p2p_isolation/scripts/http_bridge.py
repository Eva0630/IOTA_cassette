"""
http_bridge.py
HTTP version of the bridge: talks to IOTA_API's Ledger Bridge endpoints
(claim / submitted / confirm / fail / health). ledger_worker.py is unchanged;
this file only replaces MockBridge.

Environment:
  LEDGER_API_URL        base URL of IOTA_API, e.g. http://10.0.0.5:8085
  LEDGER_WORKER_TOKEN   the fixed service token created at first deployment
  AUDIT_MASTER_KEY      same key used by the other scripts

Usage:
  python3 http_bridge.py --check        test connectivity and the token
  python3 http_bridge.py --once         process one batch
  python3 http_bridge.py                run continuously
"""
import argparse
import os
import sys
from urllib.parse import quote, urlparse

import requests

import ledger_worker as lw


class BridgeAuthError(Exception):
    """The API rejected our service token. Fatal: retrying cannot help."""


class HttpBridge:
    def __init__(self, base_url, token, worker_id="worker-1",
                 lease_seconds=120, timeout=15, log=print):
        if not base_url or not token:
            raise ValueError("base_url and token are required")
        self.base = base_url.rstrip("/")
        self.headers = {"Authorization": f"Bearer {token}",
                        "Content-Type": "application/json"}
        self.worker_id = worker_id
        self.lease_seconds = lease_seconds
        self.timeout = timeout
        self.log = log

    def _call(self, method, path, body=None):
        r = requests.request(method, self.base + path, json=body,
                             headers=self.headers, timeout=self.timeout)
        if r.status_code in (401, 403):
            raise BridgeAuthError(f"HTTP {r.status_code}: the API rejected the service token")
        r.raise_for_status()
        return r.json() if r.content else {}

    def health(self):
        return self._call("GET", "/ledger/health")

    def claim(self, limit=5):
        try:
            data = self._call("POST", "/ledger/claim", {
                "worker_id": self.worker_id, "limit": limit,
                "lease_seconds": self.lease_seconds})
        except requests.RequestException as e:
            self.log(f"  API unavailable (claim): {e}")
            return []
        good = []
        for ev in data.get("events", []):
            if isinstance(ev, dict) and all(k in ev for k in ("event_id", "payload", "payload_hash")):
                good.append(ev)
            else:
                self.log("  dropped a malformed event from claim (it will be re-claimed after its lease expires)")
        return good

    def _record(self, what, eid, action, body):
        path = f"/ledger/{quote(eid, safe='')}/{action}"
        try:
            self._call("POST", path, body)
        except requests.RequestException as e:
            # The chain work is already done; the event stays PROCESSING until its lease
            # expires, then the chain-first check recovers it without resubmitting.
            raise lw.TransientError(f"could not record {what} in the API ({e})")

    def submitted(self, eid, ref):
        self._record("SUBMITTED", eid, "submitted", {"ledger_reference": ref})

    def confirm(self, eid, ref, method):
        self._record("CONFIRMED", eid, "confirm",
                     {"ledger_reference": ref, "confirmation_method": method})

    def fail(self, eid, error, retryable):
        try:
            self._call("POST", f"/ledger/{quote(eid, safe='')}/fail",
                       {"error": str(error)[:500], "retryable": bool(retryable)})
        except requests.RequestException as e:
            self.log(f"  could not report failure for {eid[:8]}: {e}")


def _warn_if_cleartext(url):
    u = urlparse(url)
    if u.scheme == "http" and u.hostname not in ("localhost", "127.0.0.1"):
        print("WARNING: the service token is sent in clear text over http://. "
              "Use HTTPS or keep this traffic on a private network.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--interval", type=int, default=10)
    ap.add_argument("--worker-id", default=os.environ.get("LEDGER_WORKER_ID", "worker-1"))
    a = ap.parse_args()

    url = os.environ.get("LEDGER_API_URL")
    token = os.environ.get("LEDGER_WORKER_TOKEN")
    if not url or not token:
        print("Set LEDGER_API_URL and LEDGER_WORKER_TOKEN first.")
        sys.exit(2)
    _warn_if_cleartext(url)
    bridge = HttpBridge(url, token, worker_id=a.worker_id)

    try:
        if a.check:
            print("API health:", bridge.health())
            return
        if not os.environ.get("AUDIT_MASTER_KEY"):
            print("AUDIT_MASTER_KEY is not set. Run: export AUDIT_MASTER_KEY=$(cat ~/.audit_master_key)")
            sys.exit(2)
        lw.run(bridge, lw.IotaChain(), once=a.once, interval=a.interval)
    except BridgeAuthError as e:
        print(f"FATAL: {e}")
        sys.exit(3)
    except requests.RequestException as e:
        print(f"Cannot reach the API: {e}")
        sys.exit(4)


if __name__ == "__main__":
    main()
