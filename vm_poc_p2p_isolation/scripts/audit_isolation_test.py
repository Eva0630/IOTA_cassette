"""
audit_isolation_test.py (v4)
UC5.3 cross-household isolation. Records are returned in chronological order.
"""
import time
import requests
from audit_chain_utils import household_to_address
from chain_time import records_in_order
from send_audit_event import send_audit_event

NODES = {
    "iri_1 (14265)": "http://localhost:14265",
    "node2 (14266)": "http://localhost:14266",
    "node3 (14267)": "http://localhost:14267",
}
HEADERS = {"Content-Type": "application/json", "X-IOTA-API-Version": "1"}

FAKE_USERS = {
    "user_A_resident": {"household_id": "A", "role": "resident"},
    "user_B_resident": {"household_id": "B", "role": "resident"},
    "admin_1": {"household_id": None, "role": "admin"},
}

SYSTEM_AUDIT_HOUSEHOLD = "SYSTEM_AUDIT"


def query_audit_log(requester_username: str, target_household: str):
    user = FAKE_USERS.get(requester_username)
    if user is None:
        return {"error": "使用者不存在，拒絕存取"}

    role = user["role"]

    if role == "resident":
        actual_target = user["household_id"]
        if target_household != user["household_id"]:
            print(f"  [隔離攔截] {requester_username} 嘗試查詢 household={target_household}，"
                  f"已被強制導回自己的 household={actual_target}")
    elif role == "admin":
        actual_target = target_household
        print(f"  [Admin稽核] {requester_username} 查閱了 household={actual_target} 的資料，"
              f"正在把這個存取行為本身上鏈...")
        send_audit_event(
            household_id=SYSTEM_AUDIT_HOUSEHOLD,
            action="admin_access",
            actor=requester_username,
            result=f"accessed_household:{actual_target}"
        )
    else:
        return {"error": "未知角色，拒絕存取"}

    address = household_to_address(actual_target)

    hash_sets = {}
    trytes_by_node = {}

    for name, uri in NODES.items():
        ft_resp = requests.post(uri, json={
            "command": "findTransactions", "addresses": [address]
        }, headers=HEADERS).json()
        hashes = ft_resp.get("hashes", [])
        hash_sets[name] = set(hashes)
        if hashes:
            gt_resp = requests.post(uri, json={
                "command": "getTrytes", "hashes": hashes
            }, headers=HEADERS).json()
            trytes_by_node[name] = gt_resp.get("trytes", [])

    all_same = len(set(frozenset(s) for s in hash_sets.values())) == 1
    consensus_ok = all_same and any(len(s) > 0 for s in hash_sets.values())

    decoded_records = []
    for name, trytes_list in trytes_by_node.items():
        decoded_records = records_in_order(trytes_list, actual_target)   # oldest first
        break

    return {
        "actual_household_queried": actual_target,
        "address_used": address,
        "multi_node_consensus": consensus_ok,
        "node_hash_counts": {k: len(v) for k, v in hash_sets.items()},
        "records": decoded_records,
    }


def query_system_audit_log():
    """Admin access log (the audit of the audit), oldest first."""
    address = household_to_address(SYSTEM_AUDIT_HOUSEHOLD)
    node1 = NODES["iri_1 (14265)"]
    ft_resp = requests.post(node1, json={
        "command": "findTransactions", "addresses": [address]
    }, headers=HEADERS).json()
    hashes = ft_resp.get("hashes", [])
    if not hashes:
        return []
    gt_resp = requests.post(node1, json={
        "command": "getTrytes", "hashes": hashes
    }, headers=HEADERS).json()
    return records_in_order(gt_resp.get("trytes", []), SYSTEM_AUDIT_HOUSEHOLD)


if __name__ == "__main__":
    print("=" * 60)
    print("情境 1：家庭 A 住戶查詢自己家的資料")
    print("=" * 60)
    print(query_audit_log("user_A_resident", target_household="A"))
    print()

    print("=" * 60)
    print("情境 2：家庭 A 住戶嘗試查詢家庭 B 的資料（應被攔截）")
    print("=" * 60)
    print(query_audit_log("user_A_resident", target_household="B"))
    print()

    print("=" * 60)
    print("情境 3：Admin 查詢家庭 B 的資料（存取行為將自動上鏈）")
    print("=" * 60)
    print(query_audit_log("admin_1", target_household="B"))
    print()

    print("等待5秒讓Admin存取紀錄透過P2P傳播...")
    time.sleep(5)

    print("=" * 60)
    print("查詢 SYSTEM_AUDIT：所有Admin存取行為的鏈上紀錄（由舊到新）")
    print("=" * 60)
    for record in query_system_audit_log():
        print(" ", record)
