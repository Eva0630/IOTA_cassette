#!/bin/bash
# 依序停鏈：compass → 等待 → node2/3 → iri（避免 milestone 發到一半被中斷）
exec >> /home/iota/stop_chain.log 2>&1
echo "[$(date '+%F %T')] stop_chain 開始"
docker stop -t 60 one-command-tangle-compass-1 || true
sleep 20
docker stop -t 30 hornet-node-2 hornet-node-3 || true
docker stop -t 30 one-command-tangle-iri-1 || true
echo "[$(date '+%F %T')] stop_chain 結束"
