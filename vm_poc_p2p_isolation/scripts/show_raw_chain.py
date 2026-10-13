"""show_raw_chain.py - what an attacker sees when querying a node directly."""
import sys
import requests
from audit_chain_utils import household_to_address, trytes_to_ascii

NODE = "http://localhost:14266"
H = {"Content-Type": "application/json", "X-IOTA-API-Version": "1"}

hid = sys.argv[1] if len(sys.argv) > 1 else "A"
addr = household_to_address(hid)
hashes = requests.post(NODE, json={"command": "findTransactions", "addresses": [addr]},
                       headers=H).json().get("hashes", [])
trytes = requests.post(NODE, json={"command": "getTrytes", "hashes": hashes},
                       headers=H).json().get("trytes", [])
print(f"household {hid}: {len(trytes)} transactions on node2")
for t in trytes:
    print("  " + trytes_to_ascii(t[:2187])[:75])
