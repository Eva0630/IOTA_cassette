"""
send_audit_event.py (v2 - 修正版)
修正重點：把 getTransactionsToApprove 拿到的真正 trunk/branch 填入交易本體，
之前的版本這裡填死是 "9"*81，導致交易變成孤立節點，永遠不會被milestone確認。

用法: python3 send_audit_event.py <household_id> <action> <actor> <result>
範例: python3 send_audit_event.py A unlock_door user_123 success
"""
import requests
import time
import sys

from audit_chain_utils import (
    household_to_address, action_to_tag, encrypt_message,
    ascii_to_trytes, pad_trytes
)

NODE_URL = "http://localhost:14265"
HEADERS = {"Content-Type": "application/json", "X-IOTA-API-Version": "1"}


def int_to_trits(value: int):
    if value == 0:
        return [0]
    trits = []
    negative = value < 0
    value = abs(value)
    while value > 0:
        value, remainder = divmod(value, 3)
        if remainder == 2:
            remainder = -1
            value += 1
        trits.append(remainder)
    if negative:
        trits = [-t for t in trits]
    return trits


def trits_to_trytes(trits) -> str:
    trytes = ""
    for i in range(0, len(trits), 3):
        chunk = trits[i:i+3]
        while len(chunk) < 3:
            chunk.append(0)
        value = chunk[0] + chunk[1]*3 + chunk[2]*9
        trytes += "9ABCDEFGHIJKLMNOPQRSTUVWXYZ"[value % 27]
    return trytes


def int_to_trytes(value: int, length: int) -> str:
    trits = int_to_trits(value)
    trits += [0] * (length * 3 - len(trits))
    return trits_to_trytes(trits)


def send_audit_event(household_id: str, action: str, actor: str, result: str):
    address = household_to_address(household_id)
    tag = action_to_tag(action)

    message_text = f'{{"household":"{household_id}","actor":"{actor}","action":"{action}","result":"{result}"}}'
    encrypted = encrypt_message(message_text, household_id)
    message_trytes = pad_trytes(ascii_to_trytes(encrypted), 2187)

    value = int_to_trytes(0, 27)
    obsolete_tag = tag
    ts = int_to_trytes(int(time.time()), 9)
    current_index = int_to_trytes(0, 9)
    last_index = int_to_trytes(0, 9)
    bundle_hash = "9" * 81
    att_ts = "9" * 9
    att_lb = "9" * 9
    att_ub = "9" * 9
    nonce = "9" * 27

    # --- 關鍵修正：先拿真正的 tip，才能組出「連結進Tangle結構」的交易 ---
    gta_resp = requests.post(NODE_URL, json={
        "command": "getTransactionsToApprove", "depth": 3
    }, headers=HEADERS).json()

    if "trunkTransaction" not in gta_resp:
        print("getTransactionsToApprove 錯誤:", gta_resp)
        return None

    trunk = gta_resp["trunkTransaction"]
    branch = gta_resp["branchTransaction"]
    print(f"   拿到真正的 tip -> trunk={trunk[:20]}... branch={branch[:20]}...")

    tx_trytes = (message_trytes + address + value + obsolete_tag + ts +
                 current_index + last_index + bundle_hash + trunk + branch +
                 tag + att_ts + att_lb + att_ub + nonce)

    att_resp = requests.post(NODE_URL, json={
        "command": "attachToTangle",
        "trunkTransaction": trunk,
        "branchTransaction": branch,
        "minWeightMagnitude": 9,
        "trytes": [tx_trytes]
    }, headers=HEADERS).json()

    if "trytes" not in att_resp:
        print("attachToTangle 錯誤:", att_resp)
        return None

    attached_trytes = att_resp["trytes"]

    requests.post(NODE_URL, json={
        "command": "broadcastTransactions", "trytes": attached_trytes
    }, headers=HEADERS)
    requests.post(NODE_URL, json={
        "command": "storeTransactions", "trytes": attached_trytes
    }, headers=HEADERS)

    print(f"✅ 送出成功: household={household_id} action={action} actor={actor} result={result}")
    print(f"   address={address[:30]}...")
    print(f"   tag={tag}")
    return attached_trytes[0]


if __name__ == "__main__":
    if len(sys.argv) != 5:
        print("用法: python3 send_audit_event.py <household_id> <action> <actor> <result>")
        print("範例: python3 send_audit_event.py A unlock_door user_123 success")
        sys.exit(1)

    household_id, action, actor, result = sys.argv[1:5]
    send_audit_event(household_id, action, actor, result)