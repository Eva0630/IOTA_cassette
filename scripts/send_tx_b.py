import requests
import time

NODE_URL = "http://localhost:14265"
TRYTE_ALPHABET = "9ABCDEFGHIJKLMNOPQRSTUVWXYZ"

def ascii_to_trytes(text: str) -> str:
    trytes = ""
    for char in text:
        code = ord(char)
        if code > 255:
            raise ValueError(f"字元超出範圍: {char}")
        first = code % 27
        second = (code - first) // 27
        trytes += TRYTE_ALPHABET[first] + TRYTE_ALPHABET[second]
    return trytes

def pad_trytes(trytes: str, length: int) -> str:
    return trytes.ljust(length, "9")[:length]

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
        trytes += TRYTE_ALPHABET[value % 27]
    return trytes

def int_to_trytes(value: int, length: int) -> str:
    trits = int_to_trits(value)
    trits += [0] * (length * 3 - len(trits))
    return trits_to_trytes(trits)

# ---- 命名規則：HOUSEHOLD + 代號，統一 pad 到 81/27 長度 ----
HOUSEHOLD_B_ADDRESS = pad_trytes("HOUSEHOLDB", 81)
TAG = pad_trytes("HOUSEHOLDB", 27)

message_text = '{household:B,actor:user456,action:view_camera,result:success}'
message_trytes = pad_trytes(ascii_to_trytes(message_text), 2187)

def build_transaction_trytes():
    signature_fragment = message_trytes
    address = HOUSEHOLD_B_ADDRESS
    value = int_to_trytes(0, 27)
    obsolete_tag = TAG
    ts = int_to_trytes(int(time.time()), 9)
    current_index = int_to_trytes(0, 9)
    last_index = int_to_trytes(0, 9)
    bundle_hash = "9" * 81
    trunk = "9" * 81
    branch = "9" * 81
    tag = TAG
    att_ts = "9" * 9
    att_lb = "9" * 9
    att_ub = "9" * 9
    nonce = "9" * 27

    return (signature_fragment + address + value + obsolete_tag + ts +
            current_index + last_index + bundle_hash + trunk + branch +
            tag + att_ts + att_lb + att_ub + nonce)

tx_trytes = build_transaction_trytes()
print("交易 trytes 長度:", len(tx_trytes))

headers = {"Content-Type": "application/json", "X-IOTA-API-Version": "1"}

gta_resp = requests.post(NODE_URL, json={
    "command": "getTransactionsToApprove",
    "depth": 3
}, headers=headers).json()
print("getTransactionsToApprove:", gta_resp)

trunk = gta_resp["trunkTransaction"]
branch = gta_resp["branchTransaction"]

att_resp = requests.post(NODE_URL, json={
    "command": "attachToTangle",
    "trunkTransaction": trunk,
    "branchTransaction": branch,
    "minWeightMagnitude": 9,
    "trytes": [tx_trytes]
}, headers=headers).json()

if "trytes" not in att_resp:
    print("attachToTangle 錯誤:", att_resp)
    exit(1)

attached_trytes = att_resp["trytes"]
print("PoW 完成，附加後的 trytes（前100字）:", attached_trytes[0][:100])

requests.post(NODE_URL, json={
    "command": "broadcastTransactions",
    "trytes": attached_trytes
}, headers=headers)

store_resp = requests.post(NODE_URL, json={
    "command": "storeTransactions",
    "trytes": attached_trytes
}, headers=headers)

print("storeTransactions 結果:", store_resp.json())
print("送出完成！Household B 的交易已上鏈。")
