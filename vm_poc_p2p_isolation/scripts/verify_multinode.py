import requests
import time

nodes = {
    "iri_1 (14265)": "http://localhost:14265",
    "node2 (14266)": "http://localhost:14266",
    "node3 (14267)": "http://localhost:14267",
}

TRYTE_ALPHABET = "9ABCDEFGHIJKLMNOPQRSTUVWXYZ"
def pad_trytes(trytes: str, length: int) -> str:
    return trytes.ljust(length, "9")[:length]

HOUSEHOLD_A_ADDRESS = pad_trytes("HOUSEHOLDA", 81)
headers = {"Content-Type": "application/json", "X-IOTA-API-Version": "1"}

print(f"查詢 address: {HOUSEHOLD_A_ADDRESS}\n")

# 給 gossip 一點時間傳播（如果剛送出馬上查，node2/node3 可能還沒收到）
print("等待 5 秒讓交易透過 P2P 傳播到其他節點...")
time.sleep(5)

results = {}

for name, uri in nodes.items():
    print(f"--- {name} ---")
    ft_resp = requests.post(uri, json={
        "command": "findTransactions",
        "addresses": [HOUSEHOLD_A_ADDRESS]
    }, headers=headers).json()

    hashes = ft_resp.get("hashes", [])
    print(f"找到 {len(hashes)} 筆交易 hash: {hashes}")

    if hashes:
        gt_resp = requests.post(uri, json={
            "command": "getTrytes",
            "hashes": hashes
        }, headers=headers).json()
        results[name] = gt_resp.get("trytes", [])
        for h, t in zip(hashes, results[name]):
            print(f"  hash={h}")
            print(f"  trytes前80字={t[:80]}")
    else:
        results[name] = []
    print()

# 比對三個節點看到的 hash 集合是否一致
hash_sets = {}
for name, uri in nodes.items():
    ft_resp = requests.post(uri, json={
        "command": "findTransactions",
        "addresses": [HOUSEHOLD_A_ADDRESS]
    }, headers=headers).json()
    hash_sets[name] = set(ft_resp.get("hashes", []))

all_same = len(set(frozenset(s) for s in hash_sets.values())) == 1

if all_same and all(len(s) > 0 for s in hash_sets.values()):
    print("✅ 三個節點對同一 address 查到完全一致的交易集合，多節點共同驗證通過！")
else:
    print("⚠️ 節點間資料尚未一致（可能還在同步中），各節點看到的 hash 數量：")
    for name, s in hash_sets.items():
        print(f"  {name}: {len(s)} 筆")
