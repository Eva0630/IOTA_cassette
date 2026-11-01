"""send_tx.py - send one plaintext test transaction for Household A (demo / smoke test).
The bundle hash is computed properly by iota_bundle.py, so milestones can confirm it
(check with check_confirmation.py)."""
import sys

import iota_bundle as ib
from audit_chain_utils import ascii_to_trytes

NODE_URL = "http://localhost:14265"

HOUSEHOLD_A_ADDRESS = ib.pad_trytes("HOUSEHOLDA", 81)
TAG = ib.pad_trytes("HOUSEHOLDA", 27)
message_text = '{household:A,actor:user123,action:unlock_door,result:success}'

if __name__ == "__main__":
    bundle_hash, txs = ib.build_message_bundle(HOUSEHOLD_A_ADDRESS, TAG, ascii_to_trytes(message_text))
    print("交易數:", len(txs), " 每筆 trytes 長度:", len(txs[0]))
    print("bundle hash:", bundle_hash)
    try:
        attached = ib.attach_and_send(NODE_URL, txs, mwm=9, depth=3, log=print)
    except ib.IriError as e:
        print("節點錯誤:", e)
        sys.exit(1)
    print("PoW 完成，附加後的 trytes（前100字）:", attached[0][:100])
    print("送出完成！")

    # 儲存 trytes 供下一步算 hash / 查詢使用
    with open("last_tx_trytes.txt", "w") as f:
        f.write(attached[0])
    print("已將完整trytes存到 last_tx_trytes.txt")
