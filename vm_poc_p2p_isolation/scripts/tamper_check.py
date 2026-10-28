#!/usr/bin/env python3
"""竄改偵測：比對「資料庫現在的事件內容」與「鏈上當初存證的雜湊」。
  tamper_check.py check
  tamper_check.py tamper [--payload-only] [--event-id ID]   (展示用：改資料庫)
  tamper_check.py restore                                   (還原展示用的竄改)
"""
import argparse, copy, json, os, subprocess
from pathlib import Path

import ledger_worker as lw

BACKUP = Path.home() / ".tamper_backup.json"
MYSQL = ('mysql -uroot -p"$MYSQL_ROOT_PASSWORD" --default-character-set=utf8mb4 '
         '-N -B -r devicemanagement 2>&1 | grep -v "Using a password"')


def sql(query):
    p = subprocess.run(["docker", "exec", "-i", "iot_mysql", "sh", "-c", MYSQL],
                       input=query, capture_output=True, text=True, encoding="utf-8")
    out = p.stdout.strip()
    if out.startswith("ERROR") or "\nERROR" in out:
        raise SystemExit("資料庫錯誤：" + out)
    return out


def esc(s):
    return s.replace("\\", "\\\\").replace("'", "\\'")


def fetch_events(where):
    q = ("SELECT JSON_OBJECT('event_id',event_id,'event_type',event_type,'status',status,"
         "'family_id',family_id,'payload_hash',payload_hash,'payload',payload) "
         f"FROM ledger_events WHERE {where} ORDER BY created_at;")
    return [json.loads(l) for l in sql(q).splitlines() if l.strip().startswith("{")]


def chain_hashes(chain, hid, eid):
    """回傳 {節點: {鏈上存證裡該事件的雜湊}}"""
    from audit_chain_utils import household_to_address, trytes_to_ascii
    from crypto_utils import read_record
    prefix = f"event_id:{eid};hash:"
    per_node = {}
    for name, url in chain.nodes.items():
        found, trytes = set(), []
        try:
            hs = chain._post(url, {"command": "findTransactions",
                                   "addresses": [household_to_address(hid)]}).get("hashes", [])
            if hs:
                trytes = chain._post(url, {"command": "getTrytes", "hashes": hs}).get("trytes", [])
        except Exception:
            pass
        for t in trytes:
            try:
                rec = json.loads(read_record(trytes_to_ascii(t[:2187]), hid))
            except Exception:
                continue
            res = str(rec.get("result", ""))
            if rec.get("action") == "ledger_anchor" and res.startswith(prefix):
                found.add(res[len(prefix):])
        per_node[name] = found
    return per_node


def cmd_check():
    chain = lw.IotaChain()
    rows = fetch_events("status IN ('SUBMITTED','CONFIRMED')")
    if not rows:
        print("沒有已上鏈的事件可檢查")
        return 0
    bad = 0
    for r in rows:
        local = lw.sha256_hex(lw.canonical_json(r["payload"]))
        stored = r["payload_hash"]
        per_node = chain_hashes(chain, str(r["family_id"]), r["event_id"])
        onchain = set().union(*per_node.values())
        tag = f"{r['event_id'][:8]} {r['event_type']}"
        if not onchain:
            bad += 1
            print(f"⚠️  {tag}  鏈上找不到存證")
            continue
        problems = []
        if local != stored:
            problems.append("事件內容與資料庫記錄的雜湊不符")
        if onchain != {local}:
            problems.append("事件內容與鏈上存證不符")
        if len({frozenset(v) for v in per_node.values()}) > 1:
            problems.append("三個節點讀到的存證不一致")
        if problems:
            bad += 1
            print(f"❌ {tag}  被竄改：" + "；".join(problems))
            print(f"     現在的內容算出 : {local}")
            print(f"     資料庫記錄的   : {stored}")
            print(f"     鏈上存證       : {', '.join(sorted(onchain))}")
        else:
            print(f"✅ {tag}  內容與鏈上存證一致  {local[:16]}…")
    print(f"結果：{len(rows) - bad}/{len(rows)} 完整" + ("" if not bad else f"，{bad} 筆異常"))
    return 1 if bad else 0


def cmd_tamper(event_id, payload_only):
    if BACKUP.exists():
        raise SystemExit(f"{BACKUP} 已存在，代表上次的竄改還沒還原。請先執行 restore。")
    where = (f"event_id='{esc(event_id)}'" if event_id
             else "event_type='SITE_GENESIS_CREATED' AND status='CONFIRMED'")
    rows = fetch_events(where)
    if not rows:
        raise SystemExit("找不到事件（需要已 CONFIRMED 的 SITE_GENESIS_CREATED）")
    r = rows[0]
    ev = copy.deepcopy(r["payload"])
    try:
        old = ev["payload"]["owner_binding"]["owner_id_hash"]
    except (KeyError, TypeError):
        raise SystemExit("這筆事件沒有 owner_binding.owner_id_hash，請改選 SITE_GENESIS_CREATED")
    fd = os.open(BACKUP, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump({"event_id": r["event_id"], "payload": r["payload"],
                   "payload_hash": r["payload_hash"]}, f, ensure_ascii=False)
    new_owner = "sha256:" + lw.sha256_hex("attacker")
    ev["payload"]["owner_binding"]["owner_id_hash"] = new_owner
    new_hash = lw.sha256_hex(lw.canonical_json(ev))
    set_hash = "" if payload_only else f", payload_hash='{new_hash}'"
    sql(f"UPDATE ledger_events SET payload=CAST('{esc(json.dumps(ev, ensure_ascii=True))}' AS JSON)"
        f"{set_hash} WHERE event_id='{esc(r['event_id'])}';")
    print(f"已竄改事件 {r['event_id'][:8]}：場域屋主 {old[:19]}… → {new_owner[:19]}…")
    print("同時重算並改掉資料庫的 payload_hash（攻擊者讓資料庫內部看起來一致）"
          if not payload_only else "只改內容，沒動 payload_hash")


def cmd_restore():
    if not BACKUP.exists():
        raise SystemExit("沒有備份檔，沒有需要還原的竄改")
    b = json.loads(BACKUP.read_text(encoding="utf-8"))
    sql(f"UPDATE ledger_events SET payload=CAST('{esc(json.dumps(b['payload'], ensure_ascii=True))}' AS JSON), "
        f"payload_hash='{esc(b['payload_hash'])}' WHERE event_id='{esc(b['event_id'])}';")
    BACKUP.rename(BACKUP.with_suffix(".restored"))
    print(f"已還原事件 {b['event_id'][:8]}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    t = sub.add_parser("tamper")
    t.add_argument("--payload-only", action="store_true")
    t.add_argument("--event-id")
    sub.add_parser("restore")
    a = ap.parse_args()
    if a.cmd == "check":
        raise SystemExit(cmd_check())
    elif a.cmd == "tamper":
        cmd_tamper(a.event_id, a.payload_only)
    else:
        cmd_restore()
