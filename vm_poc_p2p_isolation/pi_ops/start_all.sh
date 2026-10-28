#!/bin/bash
# 重開機後把 Tangle + IOTA_API 接回來，並確認 neighbor 真的連上、milestone 真的在跑。
set -u
CHAIN=/mnt/usb/IOTA_cassette/vm_poc_p2p_isolation/docker
API=/mnt/usb/IOTA_API
log() { echo "[$(date -u +%H:%M:%S)] $*"; }

# 1) 起容器
cd "$CHAIN/one-command-tangle" || exit 1
docker compose -f docker-compose.yml -f /mnt/usb/iota-arm64/docker-compose.arm64.yml up -d
cd "$CHAIN/multi-nodes" || exit 1
docker compose -f docker-compose.yml -f /mnt/usb/iota-arm64/docker-compose.arm64.multinodes.yml up -d

# 2) 等 IRI 真的 ready（不要立刻接 neighbor）
for i in $(seq 1 60); do
  curl -sf -m 2 localhost:14265 -X POST -H 'Content-Type: application/json' \
       -H 'X-IOTA-API-Version: 1' -d '{"command":"getNodeInfo"}' >/dev/null && break
  sleep 5
done

# 3) 接 neighbor，重試到三節點各 2 條
for i in $(seq 1 12); do
  cd "$CHAIN" && ./setup_neighbors.sh >/dev/null 2>&1
  ok=0
  for p in 14265 14266 14267; do
    c=$(curl -s -m 3 localhost:$p -X POST -H 'Content-Type: application/json' \
        -H 'X-IOTA-API-Version: 1' -d '{"command":"getNeighbors"}' | grep -o '"connected":true' | wc -l)
    [ "$c" -ge 2 ] && ok=$((ok+1))
  done
  [ "$ok" -eq 3 ] && { log "neighbors OK (2/2/2)"; break; }
  sleep 10
done

# 4) 起後端（monitor 是維修模式，不啟動）
cd "$API" && docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.ledger.yml up -d \
  mysql mqtt-broker mqtt-server api api-mqtt-bridge node-red

log done
