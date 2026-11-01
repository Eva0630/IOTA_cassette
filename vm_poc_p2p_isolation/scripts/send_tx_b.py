"""send_tx_b.py - send one plaintext test transaction for Household B (demo / smoke test).
The bundle hash is computed properly by iota_bundle.py, so milestones can confirm it."""
import sys

import iota_bundle as ib
from audit_chain_utils import ascii_to_trytes

NODE_URL = "http://localhost:14265"

# ---- 命名規則：HOUSEHOLD + 代號，統一 pad 到 81/27 長度 ----
HOUSEHOLD_B_ADDRESS = ib.pad_trytes("HOUSEHOLDB", 81)
TAG = ib.pad_trytes("HOUSEHOLDB", 27)
message_text = '{household:B,actor:user456,action:view_camera,result:success}'

if __name__ == "__main__":
    bundle_hash, txs = ib.build_message_bundle(HOUSEHOLD_B_ADDRESS, TAG, ascii_to_trytes(message_text))
    print("交易數:", len(txs), " 每筆 trytes 長度:", len(txs[0]))
    print("bundle hash:", bundle_hash)
    try:
        attached = ib.attach_and_send(NODE_URL, txs, mwm=9, depth=3, log=print)
    except ib.IriError as e:
        print("節點錯誤:", e)
        sys.exit(1)
    print("PoW 完成，附加後的 trytes（前100字）:", attached[0][:100])
    print("送出完成！Household B 的交易已上鏈。")
