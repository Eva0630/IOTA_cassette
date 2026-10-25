#!/bin/bash
# demo 重置：資料庫、閘道身分、鏈全部回到乾淨起點，再建立 demo 資料
#   ~/demo_reset.sh --check   只做事前檢查，不改任何東西
#   ~/demo_reset.sh           正式重置
set -Eeuo pipefail
trap 'echo "❌ 失敗：第 $LINENO 行"' ERR

### ---- demo 內容（要改就改這裡）----
DEMO_USER="Admin0123456789"
DEMO_EMAIL="admin@example.com"
FAMILY_NAME="My Sweet Home"
GATEWAY_NAME="My Sweet Home Gateway"
DOOR_ID="${DOOR_ID:-DOOR_LOCK_001}"   # 接實體 ESP32：DOOR_ID=E8:31:CD:82:80:C8 ~/demo_reset.sh
DEVICES=(                              # device_id|顯示名稱|device_type
  "${DOOR_ID}|前門智慧鎖|smart_lock"
  "SAFE_001|保險箱|smart_lock"
)
### ----------------------------------

API=http://127.0.0.1:8091
BASELINE=/home/iota/devicemanagement-clean-baseline-20261024-1156.sql
APIDIR=/mnt/usb/IOTA_API/API
ARCHIVE=/mnt/usb/gateway_runtime_archive
TS=$(date +%Y%m%d-%H%M)
MYQ='mysql -uroot -p"$MYSQL_ROOT_PASSWORD" --default-character-set=utf8mb4 devicemanagement'

die(){ echo "❌ $*"; exit 1; }
step(){ echo; echo "== $* =="; }
dbq(){ { docker exec -i iot_mysql sh -c "$MYQ -N -B" 2>&1 || true; } | grep -v 'Using a password' || true; }

mk(){ python3 - <<'PY'
import json, os
p = {k[2:]: v for k, v in os.environ.items() if k.startswith("P_")}
if "family_id" in p:
    p["family_id"] = int(p["family_id"])
print(json.dumps({"payload": p}, ensure_ascii=False))
PY
}

post(){
  local out code body
  out=$(curl -s -m 60 -w '\n%{http_code}' -X POST "$API/$1" -H 'Content-Type: application/json' --data-binary @-)
  code=${out##*$'\n'}; body=${out%$'\n'*}
  echo "[$1] HTTP $code  $(echo "$body" | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get("status"),"-",d.get("msg"))' 2>/dev/null)"
  [ "${code:0:1}" = "2" ] || { echo "$body" | head -c 600; echo; exit 1; }
}

chain_ok(){ python3 - <<'PY'
import requests, sys
H = {"Content-Type": "application/json", "X-IOTA-API-Version": "1"}
vals = []
for p in (14265, 14266, 14267):
    try:
        d = requests.post(f"http://localhost:{p}", json={"command": "getNodeInfo"}, headers=H, timeout=5).json()
        vals.append((d["latestMilestoneIndex"], d["latestSolidSubtangleMilestoneIndex"]))
    except Exception:
        sys.exit(1)
print("   節點 (latest, solid):", vals)
ok = all(l == s and l >= 3 for l, s in vals) and max(l for l, _ in vals) - min(l for l, _ in vals) <= 1
sys.exit(0 if ok else 1)
PY
}

preflight(){
  [ -f "$BASELINE" ] || die "找不到基準備份 $BASELINE"
  [ -x /home/iota/reset_chain.sh ] || die "找不到 ~/reset_chain.sh"
  [ -x /home/iota/tamper_run.sh ] || die "找不到 ~/tamper_run.sh"
  [ "$(docker inspect -f '{{.State.Running}}' iot_mysql 2>/dev/null)" = "true" ] || die "iot_mysql 沒在跑"
  [ "$(docker inspect -f '{{.State.Running}}' iot_api 2>/dev/null)" = "true" ] || die "iot_api 沒在跑"
  systemctl cat ledger-worker.service >/dev/null 2>&1 || die "找不到 ledger-worker.service"
  [ ! -e /home/iota/.tamper_backup.json ] || die "上次的竄改展示還沒 restore"
  echo "目前資料筆數 (users, families, devices, ledger_events)："
  echo "SELECT (SELECT COUNT(*) FROM users),(SELECT COUNT(*) FROM families),(SELECT COUNT(*) FROM devices),(SELECT COUNT(*) FROM ledger_events);" | dbq
  echo "將建立：帳號 $DEMO_USER／場域 $FAMILY_NAME"
  for d in "${DEVICES[@]}"; do echo "  裝置：$d"; done
  echo "預檢通過"
}

preflight
[ "${1:-}" = "--check" ] && exit 0

cat <<MSG

⚠️  這會清空：
  - 資料庫 devicemanagement 的所有資料（帳號、場域、裝置、稽核紀錄、ledger 事件）
  - 私有鏈（舊資料搬到 docker/_old-*，不會刪除）
  - 閘道身分（封存到 $ARCHIVE，之後使用新的閘道 ID）
MSG
read -rp "確定要重置請輸入 RESET： " ans
[ "$ans" = "RESET" ] || die "已取消"
read -rsp "設定 $DEMO_USER 的密碼（輸入時不顯示）： " PW; echo
read -rsp "再輸入一次： " PW2; echo
[ -n "$PW" ] && [ "$PW" = "$PW2" ] || die "密碼空白或兩次不一致"
unset PW2

sudo -v
( while true; do sudo -n true; sleep 60; done ) &
KA=$!
trap 'kill $KA 2>/dev/null || true' EXIT

step "1/8 停止 Worker"
sudo systemctl stop ledger-worker.service

step "2/8 備份目前資料庫"
PRE=/home/iota/devicemanagement-pre-reset-$TS.sql
docker exec iot_mysql sh -c 'mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" --single-transaction devicemanagement' 2>/dev/null > "$PRE"
chmod 600 "$PRE"; [ -s "$PRE" ] || die "備份失敗"
echo "已備份到 $PRE"

step "3/8 還原乾淨的資料庫"
if ! out=$(docker exec -i iot_mysql sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" devicemanagement' < "$BASELINE" 2>&1); then
  echo "$out"; die "還原失敗，可用 $PRE 還原"
fi
cnt=$(echo "SELECT (SELECT COUNT(*) FROM users)+(SELECT COUNT(*) FROM families)+(SELECT COUNT(*) FROM devices)+(SELECT COUNT(*) FROM ledger_events)+(SELECT COUNT(*) FROM audit_logs);" | dbq | tr -d '[:space:]')
[ "$cnt" = "0" ] || die "還原後資料不是空的 ($cnt)"
echo "資料庫已清空"

step "4/8 封存舊的閘道身分"
sudo mkdir -p "$ARCHIVE"; sudo chmod 700 "$ARCHIVE"
if [ -d "$APIDIR/gateway_runtime" ]; then
  sudo mv "$APIDIR/gateway_runtime" "$ARCHIVE/$TS"
  echo "已封存到 $ARCHIVE/$TS"
fi

step "5/8 重建私有鏈"
/home/iota/reset_chain.sh
for i in $(seq 1 30); do
  chain_ok && break
  [ "$i" = "30" ] && die "鏈沒有正常前進，請先處理再繼續"
  sleep 10
done

step "6/8 新閘道、註冊、場域初始化、裝置配對"
PROV=$(docker exec -w /app iot_api python -u gateway_initialization/provision_gateway_identity.py)
TOKEN=$(echo "$PROV" | python3 -c 'import sys,json; print(json.load(sys.stdin)["data"]["initialization_token"])') || die "provision 失敗"
P_user_id="$DEMO_USER" P_username="Admin" P_password="$PW" P_email="$DEMO_EMAIL" P_phone_number="0900000000" mk | post register
P_user_id="$DEMO_USER" P_password="$PW" P_family_name="$FAMILY_NAME" P_gateway_name="$GATEWAY_NAME" P_initialization_token="$TOKEN" mk | post gateway_initialize
unset TOKEN PW
FID=$(echo "SELECT family_id FROM ledger_events WHERE event_type='SITE_GENESIS_CREATED' LIMIT 1;" | dbq | tr -d '[:space:]')
GWID=$(echo "SELECT gateway_id FROM ledger_events WHERE event_type='SITE_GENESIS_CREATED' LIMIT 1;" | dbq | tr -d '[:space:]')
[ -n "$FID" ] && [ -n "$GWID" ] || die "讀不到 family_id／gateway_id"
echo "family_id=$FID gateway_id=$GWID"
for d in "${DEVICES[@]}"; do
  IFS='|' read -r did dname dtype <<<"$d"
  P_owner_user_id="$DEMO_USER" P_family_id="$FID" P_gateway_id="$GWID" P_device_id="$did" P_device_name="$dname" P_device_type="$dtype" mk | post device_pair
done

step "7/8 啟動 Worker，等待事件上鏈"
sudo systemctl start ledger-worker.service
EXPECT=$(( 1 + ${#DEVICES[@]} ))
conf=0
for i in $(seq 1 60); do
  conf=$(echo "SELECT COUNT(*) FROM ledger_events WHERE status='CONFIRMED';" | dbq | tr -d '[:space:]')
  dead=$(echo "SELECT COUNT(*) FROM ledger_events WHERE status='DEAD_LETTER';" | dbq | tr -d '[:space:]')
  echo "   已確認 ${conf:-0} / $EXPECT"
  [ "${dead:-0}" = "0" ] || die "有事件進入 DEAD_LETTER，請檢查 journalctl -u ledger-worker"
  [ "${conf:-0}" = "$EXPECT" ] && break
  sleep 10
done
[ "${conf:-0}" = "$EXPECT" ] || die "等待逾時，事件還沒全部確認"

step "8/8 竄改偵測基準檢查"
/home/iota/tamper_run.sh check

echo
echo "✅ 重置完成：帳號 $DEMO_USER／場域 $FAMILY_NAME／閘道 $GWID／family_id $FID"
