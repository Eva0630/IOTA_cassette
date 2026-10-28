#!/bin/bash
# 重建私有 Tangle：保留 layers / .env / snapshot，清掉各節點 db 與 Compass state
set -euo pipefail
CHAIN=/mnt/usb/IOTA_cassette/vm_poc_p2p_isolation/docker
ARM=/mnt/usb/iota-arm64
OLD=$CHAIN/_old-$(date +%Y%m%d-%H%M)
ONE="docker compose -f $CHAIN/one-command-tangle/docker-compose.yml -f $ARM/docker-compose.arm64.yml"
MULTI="docker compose -f $CHAIN/multi-nodes/docker-compose.yml -f $ARM/docker-compose.arm64.multinodes.yml"
log(){ echo "[$(date +%H:%M:%S)] $*"; }
idx(){ curl -s -m 3 localhost:$1 -X POST -H 'Content-Type: application/json' -H 'X-IOTA-API-Version: 1' \
  -d '{"command":"getNodeInfo"}' | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['latestMilestoneIndex'],d['latestSolidSubtangleMilestoneIndex'])" 2>/dev/null || echo "- -"; }

log "1) 停止並移除舊容器"
(cd $CHAIN/one-command-tangle && $ONE down)
(cd $CHAIN/multi-nodes && $MULTI down)

log "2) 舊資料移到 $OLD"
sudo mkdir -p "$OLD"
sudo mv $CHAIN/one-command-tangle/db    "$OLD/one-db"
sudo mv $CHAIN/one-command-tangle/state "$OLD/one-state"
sudo mv $CHAIN/multi-nodes/node2/db     "$OLD/node2-db"
sudo mv $CHAIN/multi-nodes/node3/db     "$OLD/node3-db"
sudo mkdir -p $CHAIN/one-command-tangle/db $CHAIN/one-command-tangle/state \
              $CHAIN/multi-nodes/node2/db $CHAIN/multi-nodes/node3/db

log "3) 啟動三個 IRI 節點"
(cd $CHAIN/one-command-tangle && $ONE up -d iri)
(cd $CHAIN/multi-nodes && $MULTI up -d)
for p in 14265 14266 14267; do
  for i in $(seq 1 60); do curl -sf -m 2 localhost:$p -X POST -H 'Content-Type: application/json' \
    -H 'X-IOTA-API-Version: 1' -d '{"command":"getNodeInfo"}' >/dev/null && break; sleep 5; done
done
log "4) 接 neighbor"
$CHAIN/setup_neighbors.sh

log "5) Compass 第一次啟動（-bootstrap）"
(cd $CHAIN/one-command-tangle && EXTRA_COMPASS_FLAGS="-bootstrap" $ONE up -d compass)
for i in $(seq 1 60); do
  read l s <<<"$(idx 14265)"
  echo "node1 latest=$l solid=$s"
  [ "$l" != "-" ] && [ "$l" -ge 2 ] 2>/dev/null && break
  sleep 5
done
docker logs --tail 10 one-command-tangle-compass-1 2>&1

log "6) 拿掉 -bootstrap 重新啟動 Compass"
(cd $CHAIN/one-command-tangle && EXTRA_COMPASS_FLAGS="" $ONE up -d compass)
sleep 100
for p in 14265 14266 14267; do echo "port $p (latest solid): $(idx $p)"; done
docker logs --tail 8 one-command-tangle-compass-1 2>&1
log "完成：若三節點 latest/solid 持續增加，鏈已重建成功"
