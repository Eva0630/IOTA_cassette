"""
send_audit_event.py (v3)
v2: trunk/branch come from getTransactionsToApprove.
v3: the bundle hash is now really computed (Kerl over the bundle essence, see
    iota_bundle.py). Before this, bundle was "9"*81, IRI treated the transaction as an
    invalid bundle and milestones could never confirm it.

用法: python3 send_audit_event.py <household_id> <action> <actor> <result>
範例: python3 send_audit_event.py A unlock_door user_123 success
"""
import sys
import time

import iota_bundle as ib
from iota_bundle import int_to_trytes  # noqa: F401  (kept for older imports, e.g. test_chain_time)
from audit_chain_utils import (
    household_to_address, action_to_tag, encrypt_message, ascii_to_trytes
)

NODE_URL = "http://localhost:14265"
MWM = 9
DEPTH = 3


def build_audit_bundle(household_id: str, action: str, actor: str, result: str, timestamp=None):
    """Return (bundle_hash, [tx trytes]) for one encrypted audit record (not yet attached)."""
    address = household_to_address(household_id)
    tag = action_to_tag(action)
    message_text = f'{{"household":"{household_id}","actor":"{actor}","action":"{action}","result":"{result}"}}'
    encrypted = encrypt_message(message_text, household_id)   # <= 1093 chars -> one transaction
    return ib.build_message_bundle(address, tag, ascii_to_trytes(encrypted),
                                   timestamp if timestamp is not None else int(time.time()))


def send_audit_event(household_id: str, action: str, actor: str, result: str, node_url: str = NODE_URL):
    """Build, attach (PoW on the node), store and broadcast. Returns the tail transaction
    trytes, or None if the node rejected it."""
    bundle_hash, txs = build_audit_bundle(household_id, action, actor, result)
    try:
        attached = ib.attach_and_send(node_url, txs, mwm=MWM, depth=DEPTH, log=print)
    except ib.IriError as e:
        print("節點拒絕交易:", e)
        return None

    print(f"✅ 送出成功: household={household_id} action={action} actor={actor} result={result}")
    print(f"   address={txs[0][2187:2217]}...")
    print(f"   tag={txs[0][2592:2619]}")
    print(f"   bundle={bundle_hash}")
    return attached[0]


if __name__ == "__main__":
    if len(sys.argv) != 5:
        print("用法: python3 send_audit_event.py <household_id> <action> <actor> <result>")
        print("範例: python3 send_audit_event.py A unlock_door user_123 success")
        sys.exit(1)

    household_id, action, actor, result = sys.argv[1:5]
    send_audit_event(household_id, action, actor, result)
