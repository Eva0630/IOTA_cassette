"""
check_confirmation.py - 驗證交易是否被 Coordinator 發的 milestone 確認
用 getInclusionStates，帶入目前的 latestSolidSubtangleMilestone 當比對基準
（實作在 iota_bundle.inclusion_states；ledger_worker 的 MILESTONE 判定用的是同一個函式）

用法:
  python3 check_confirmation.py                 查 household A 的 address 下所有交易
  python3 check_confirmation.py <household_id>  查指定 household（例如 ledger 的 family_id 12）
  python3 check_confirmation.py --hash <TXHASH> [<TXHASH> ...]

注意：bundle hash 修正（iota_bundle.py）之前送出的交易 bundle 欄位是 9*81，
是無效 bundle，永遠不會被確認；只有修正後送出的新交易才可能顯示「已確認」。
"""
import sys

import iota_bundle as ib

NODES = {
    "iri_1 (14265)": "http://localhost:14265",
    "node2 (14266)": "http://localhost:14266",
    "node3 (14267)": "http://localhost:14267",
}


def hashes_for(uri, args):
    if args and args[0] == "--hash":
        return args[1:]
    from audit_chain_utils import household_to_address
    hid = args[0] if args else "A"
    return ib.iri_call(uri, {"command": "findTransactions",
                             "addresses": [household_to_address(hid)]}).get("hashes", [])


if __name__ == "__main__":
    args = sys.argv[1:]
    for name, uri in NODES.items():
        print(f"--- {name} ---")
        try:
            hashes = hashes_for(uri, args)
            if not hashes:
                print("  沒有找到交易\n")
                continue
            _, ms_index = ib.latest_solid_milestone(uri)
            states = ib.inclusion_states(uri, hashes)
        except Exception as e:
            print(f"  查詢失敗: {e}\n")
            continue
        for h, state in zip(hashes, states):
            status = "✅ 已確認 (confirmed)" if state else "⏳ 尚未確認 (pending)"
            print(f"  tx={h[:20]}... solid_milestone_index={ms_index} -> {status}")
        print()
