"""
第2步：驗證交易是否被 Coordinator 發的 milestone 確認
用 getInclusionStates，帶入目前的 latestSolidSubtangleMilestone 當比對基準
"""
import requests

TRYTE_ALPHABET = "9ABCDEFGHIJKLMNOPQRSTUVWXYZ"
HEADERS = {"Content-Type": "application/json", "X-IOTA-API-Version": "1"}

def pad_trytes(trytes: str, length: int) -> str:
    return trytes.ljust(length, "9")[:length]

NODES = {
    "iri_1 (14265)": "http://localhost:14265",
    "node2 (14266)": "http://localhost:14266",
    "node3 (14267)": "http://localhost:14267",
}

# 查 Household A 的交易 hash
from audit_chain_utils import household_to_address
address = household_to_address("A")

for name, uri in NODES.items():
    print(f"--- {name} ---")

    # 1. 找出這個 address 下的所有交易 hash
    ft_resp = requests.post(uri, json={
        "command": "findTransactions",
        "addresses": [address]
    }, headers=HEADERS).json()
    hashes = ft_resp.get("hashes", [])
    if not hashes:
        print("  沒有找到交易")
        continue

    # 2. 拿目前節點認定的最新 milestone hash 當比對基準
    node_info = requests.post(uri, json={"command": "getNodeInfo"}, headers=HEADERS).json()
    latest_milestone = node_info.get("latestSolidSubtangleMilestone")
    milestone_index = node_info.get("latestSolidSubtangleMilestoneIndex")

    # 3. 查 inclusion state
    gis_resp = requests.post(uri, json={
        "command": "getInclusionStates",
        "transactions": hashes,
        "tips": [latest_milestone]
    }, headers=HEADERS).json()

    states = gis_resp.get("states", [])
    for h, state in zip(hashes, states):
        status = "✅ 已確認 (confirmed)" if state else "⏳ 尚未確認 (pending)"
        print(f"  tx={h[:20]}... milestone_index={milestone_index} -> {status}")
    print()
