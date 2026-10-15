#!/usr/bin/env python3
"""
demo.py - end-to-end demonstration of the household audit-log system.

Usage:
  python3 demo.py --check    read-only: nodes, milestones, neighbors, Coordinator alive
  python3 demo.py            full demo (pauses between sections when run in a terminal)
  python3 demo.py --fast     full demo without pauses

Each full run writes 4 PERMANENT transactions (3 events + 1 admin-access record)
under brand-new demo households, so it never touches your real test data.
"""
import argparse
import contextlib
import io
import os
import sys
import time

import requests

NODES = {
    "node1": "http://localhost:14265",
    "node2": "http://localhost:14266",
    "node3": "http://localhost:14267",
}
HEADERS = {"Content-Type": "application/json", "X-IOTA-API-Version": "1"}
results = []


def rpc(url, body, timeout=15):
    return requests.post(url, json=body, headers=HEADERS, timeout=timeout).json()


def say(msg=""):
    print(msg, flush=True)


def title(n, text):
    say()
    say("=" * 66)
    say(f"  {n}. {text}")
    say("=" * 66)


def check(name, ok, detail=""):
    results.append((name, bool(ok)))
    say(f"  {'✅' if ok else '❌'} {name}" + (f"   ({detail})" if detail else ""))


def pause(args):
    if not args.fast and sys.stdin.isatty():
        input("\n  [按 Enter 繼續] ")


def preflight():
    info = {}
    for name, url in NODES.items():
        try:
            info[name] = rpc(url, {"command": "getNodeInfo"}, 6)
        except Exception:
            info[name] = None
    for name, i in info.items():
        if i:
            say(f"  {name}: {i.get('appName')} {i.get('appVersion')}   milestone={i.get('latestSolidSubtangleMilestoneIndex')}   neighbors={i.get('neighbors')}")
        else:
            say(f"  {name}: 無回應")
    up = all(info.values())
    check("三個節點都有回應", up)
    if not up:
        return False
    ms = [i["latestSolidSubtangleMilestoneIndex"] for i in info.values()]
    check("三節點 milestone 同步（差距 ≤ 3）", max(ms) - min(ms) <= 3, str(ms))
    check("每個節點都連著另外兩個節點", all(i.get("neighbors") == 2 for i in info.values()))
    return all(ok for _, ok in results)


def milestone_advances(timeout=50):
    first = rpc(NODES["node1"], {"command": "getNodeInfo"})["latestSolidSubtangleMilestoneIndex"]
    say(f"  等待 Coordinator 發出新的 milestone（最多 {timeout} 秒）...")
    end = time.time() + timeout
    now = first
    while time.time() < end:
        time.sleep(3)
        now = rpc(NODES["node1"], {"command": "getNodeInfo"})["latestSolidSubtangleMilestoneIndex"]
        if now > first:
            break
    check("Coordinator 持續發出 milestone", now > first, f"{first} -> {now}")


def fetch_trytes(url, household_id):
    from audit_chain_utils import household_to_address
    addr = household_to_address(household_id)
    hashes = rpc(url, {"command": "findTransactions", "addresses": [addr]}).get("hashes", [])
    if not hashes:
        return []
    return rpc(url, {"command": "getTrytes", "hashes": hashes}).get("trytes", [])


def send(household_id, action, actor, result):
    from send_audit_event import send_audit_event
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            r = send_audit_event(household_id, action, actor, result)
        return r is not None
    except Exception as e:
        say(f"     送出失敗: {e}")
        return False


def wait_replicated(expected, timeout=90):
    end = time.time() + timeout
    while True:
        counts = {n: {h: len(fetch_trytes(u, h)) for h in expected} for n, u in NODES.items()}
        if all(counts[n][h] == expected[h] for n in NODES for h in expected):
            return True, counts
        if time.time() > end:
            return False, counts
        time.sleep(3)


def joined(res):
    return " ".join(res.get("records", []))


def show_records(res):
    for rec in res.get("records", []):
        say(f"     {rec}")


def run_demo(args):
    from audit_chain_utils import trytes_to_ascii
    from chain_time import format_time, tx_timestamp
    from crypto_utils import read_record
    import audit_isolation_test as iso

    run = time.strftime("%m%d%H%M%S")
    A, B = f"DEMO{run}A", f"DEMO{run}B"
    iso.FAKE_USERS["alice"] = {"household_id": A, "role": "resident"}
    iso.FAKE_USERS["bob"] = {"household_id": B, "role": "resident"}

    title(1, "系統狀態：三個節點的私有 Tangle")
    if not preflight():
        say("\n  節點狀態不正常，先不送出任何資料。請先執行 setup_neighbors.sh 後再試。")
        return False
    say(f"\n  本次示範使用全新的家庭：A = {A}，B = {B}")
    pause(args)

    title(2, "兩個家庭各自把操作紀錄寫上鏈")
    events = [(A, "unlock_door", "alice", "success", "家庭 A  alice 開門"),
              (A, "view_camera", "alice", "success", "家庭 A  alice 查看攝影機"),
              (B, "alert_triggered", "bob", "success", "家庭 B  bob 觸發警報")]
    sent = []
    for hid, action, actor, result, label in events:
        ok = send(hid, action, actor, result)
        sent.append(ok)
        say(f"  {'✅' if ok else '❌'} {label}")
        time.sleep(1.2)          # distinct timestamps (they are stored in seconds)
    check("三筆事件都成功上鏈", all(sent))
    if not all(sent):
        return False
    pause(args)

    title(3, "多節點共同見證：三個節點看到同樣的資料")
    say("  等待資料透過 P2P 傳播到所有節點...")
    ok, counts = wait_replicated({A: 2, B: 1})
    say(f"\n  {'':14}{'node1':>8}{'node2':>8}{'node3':>8}")
    for hid, label in ((A, "家庭 A"), (B, "家庭 B")):
        say(f"  {label:12}{counts['node1'][hid]:>8}{counts['node2'][hid]:>8}{counts['node3'][hid]:>8}")
    check("三個節點的交易數量一致", ok)
    pause(args)

    title(4, "如果有人繞過系統、直接問節點，只會看到密文")
    trs = fetch_trytes(NODES["node2"], A)
    say("  node2 上家庭 A 位址底下的原始內容（節點回傳的順序）：")
    for t in trs:
        say(f"     [{format_time(tx_timestamp(t))}] {trytes_to_ascii(t[:2187])[:52]}...")
    raws = [trytes_to_ascii(t[:2187]) for t in trs]
    check("鏈上內容是密文（看不到任何明文）",
          bool(raws) and all(r.startswith("ENC1:") for r in raws) and "unlock_door" not in " ".join(raws))
    check("用家庭 A 自己的金鑰可以解開", bool(raws) and A in read_record(raws[0], A))
    check("用家庭 B 的金鑰解不開家庭 A 的資料",
          bool(raws) and read_record(raws[0], B).startswith("[UNREADABLE"))
    times = [tx_timestamp(t) for t in trs]
    say(f"\n  節點回傳的順序{'剛好' if times == sorted(times) else '不是'}時間順序，系統查詢時會依交易內的時間重新排序。")
    pause(args)

    title(5, "跨屋隔離：住戶只能查自己家")
    say("  [alice（家庭 A 住戶）查詢自己家]")
    r1 = iso.query_audit_log("alice", A)
    show_records(r1)
    say("\n  [alice 嘗試查詢家庭 B —— 模擬竄改請求]")
    r2 = iso.query_audit_log("alice", B)
    show_records(r2)
    say("\n  [bob（家庭 B 住戶）查詢自己家]")
    r3 = iso.query_audit_log("bob", B)
    show_records(r3)
    say()
    check("alice 只看到家庭 A 的資料", "alice" in joined(r1) and "bob" not in joined(r1) and len(r1["records"]) == 2)
    check("alice 要求查家庭 B，仍然只看到家庭 A",
          r2.get("actual_household_queried") == A and "bob" not in joined(r2))
    check("bob 只看到家庭 B 的資料", "bob" in joined(r3) and "alice" not in joined(r3))
    check("查詢時三個節點的結果一致", all(r.get("multi_node_consensus") for r in (r1, r2, r3)))
    recs = r1.get("records", [])
    check("紀錄依時間由舊到新排列",
          len(recs) == 2 and "unlock_door" in recs[0] and "view_camera" in recs[1])
    pause(args)

    title(6, "Admin 可以查任何家庭，但查詢本身會自動上鏈留痕")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        r4 = iso.query_audit_log("admin_1", B)
    say("  [admin_1 查詢家庭 B]")
    show_records(r4)
    trail = [x for x in iso.query_system_audit_log() if f"accessed_household:{B}" in x]
    say("\n  [稽核的稽核：SYSTEM_AUDIT 裡關於這次查詢的鏈上紀錄]")
    for x in trail:
        say(f"     {x}")
    say()
    check("Admin 可以看到家庭 B 的資料", "bob" in joined(r4))
    check("Admin 的這次查詢已經自動上鏈", len(trail) == 1)
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="read-only health check")
    ap.add_argument("--fast", action="store_true", help="do not pause between sections")
    args = ap.parse_args()

    if not os.environ.get("AUDIT_MASTER_KEY"):
        print("AUDIT_MASTER_KEY is not set. Run: export AUDIT_MASTER_KEY=$(cat ~/.audit_master_key)")
        sys.exit(2)

    if args.check:
        title(0, "展出前檢查（只讀取，不會寫入任何資料）")
        ok = preflight()
        if ok:
            milestone_advances()
        good = all(o for _, o in results)
        say("\n  " + ("✅ 一切正常，可以展出" if good else "❌ 有項目未通過，請先處理"))
        sys.exit(0 if good else 1)

    started = run_demo(args)
    title(7, "驗證結果")
    for name, ok in results:
        say(f"  {'✅' if ok else '❌'} {name}")
    passed = sum(1 for _, o in results if o)
    say(f"\n  共 {len(results)} 項，通過 {passed} 項")
    if started:
        say("  （本次示範的 4 筆資料已永久寫在鏈上）")
    sys.exit(0 if started and passed == len(results) else 1)


if __name__ == "__main__":
    main()
