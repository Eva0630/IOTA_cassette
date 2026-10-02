"""
audit_isolation_test.py (v3)
UC5.3 跨屋隔離 - Admin存取行為本身也自動上鏈
"""
import requests
from audit_chain_utils import household_to_address, trytes_to_ascii, decrypt_message
from send_audit_event import send_audit_event   # 新增：拿來把Admin存取行為上鏈

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

SYSTEM_AUDIT_HOUSEHOLD = "SYSTEM_AUDIT"  # Admin存取行為專屬的household分類


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
        # 關鍵：Admin的查閱行為本身也送一筆交易上鏈，無法被竄改或刪除
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
        for t in trytes_list:
            decrypted = decrypt_message(t[:2187], actual_target)
            decoded_records.append(trytes_to_ascii(decrypted))
        break

    return {
        "actual_household_queried": actual_target,
        "address_used": address,
        "multi_node_consensus": consensus_ok,
        "node_hash_counts": {k: len(v) for k, v in hash_sets.items()},
        "records": decoded_records,
    }


def query_system_audit_log():
    """查詢SYSTEM_AUDIT這個分類，看所有Admin存取紀錄（模擬更高層級稽核者的視角）"""
    address = household_to_address(SYSTEM_AUDIT_HOUSEHOLD)
    ft_resp = requests.post(NODES["iri_1 (14265)"], json={
        "command": "findTransactions", "addresses": [address]
    }, headers=HEADERS).json()
    hashes = ft_resp.get("hashes", [])
    if not hashes:
        return []
    gt_resp = requests.post(NODES["iri_1 (14265)"], json={
        "command": "getTrytes", "hashes": hashes
    }, headers=HEADERS).json()
    return [trytes_to_ascii(t[:2187]) for t in gt_resp.get("trytes", [])]


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

    import time
    print("等待5秒讓Admin存取紀錄透過P2P傳播...")
    time.sleep(5)

    print("=" * 60)
    print("查詢 SYSTEM_AUDIT：所有Admin存取行為的鏈上紀錄")
    print("=" * 60)
    for record in query_system_audit_log():
        print(" ", record)