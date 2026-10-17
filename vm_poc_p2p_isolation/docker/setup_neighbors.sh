#!/bin/bash
# setup_neighbors.sh
# Re-add neighbors for the 3-node private tangle and verify they are connected.
# IRI does not persist neighbors, so run this after every restart.
#
# Waiting times (seconds). Defaults suit a native x86 machine.
# Under QEMU emulation (e.g. Raspberry Pi 5) IRI starts much slower, so use e.g.:
#   READY_WAIT=600 CONNECT_WAIT=300 ./setup_neighbors.sh
#   (or simply: WAIT_SECONDS=600 ./setup_neighbors.sh  -> sets both)

WAIT_SECONDS="${WAIT_SECONDS:-}"
READY_WAIT="${READY_WAIT:-${WAIT_SECONDS:-60}}"      # per node: wait until the API answers
CONNECT_WAIT="${CONNECT_WAIT:-${WAIT_SECONDS:-60}}"  # wait until all neighbors are connected
READY_POLL="${READY_POLL:-2}"
CONNECT_POLL="${CONNECT_POLL:-5}"

N1_API="${N1_API:-http://localhost:14265}"
N2_API="${N2_API:-http://localhost:14266}"
N3_API="${N3_API:-http://localhost:14267}"
N1_IP="${N1_IP:-172.28.0.1}"   # node1 uses host network -> reached via the bridge gateway
N2_IP="${N2_IP:-172.28.0.2}"
N3_IP="${N3_IP:-172.28.0.3}"
GOSSIP_PORT="${GOSSIP_PORT:-15600}"

for v in READY_WAIT CONNECT_WAIT READY_POLL CONNECT_POLL; do
  case "${!v}" in ''|*[!0-9]*) echo "ERROR: $v must be a whole number of seconds (got '${!v}')"; exit 2;; esac
done

api() {
  curl -s --max-time 5 -X POST "$1" \
    -H 'Content-Type: application/json' \
    -H 'X-IOTA-API-Version: 1' -d "$2"
}

wait_ready() {
  local start=$SECONDS
  while :; do
    api "$1" '{"command":"getNodeInfo"}' | grep -q '"appName"' && return 0
    if [ $((SECONDS - start)) -ge "$READY_WAIT" ]; then
      echo "ERROR: $1 is not responding after ${READY_WAIT}s (slow start? try READY_WAIT=600)"
      return 1
    fi
    sleep "$READY_POLL"
  done
}

add_neighbors() {   # $1=api  $2,$3=neighbor IPs
  api "$1" "{\"command\":\"addNeighbors\",\"uris\":[\"tcp://$2:$GOSSIP_PORT\",\"tcp://$3:$GOSSIP_PORT\"]}" >/dev/null
}

connected_count() {
  api "$1" '{"command":"getNeighbors"}' | grep -o '"connected":true' | wc -l
}

for a in "$N1_API" "$N2_API" "$N3_API"; do
  wait_ready "$a" || exit 1
done

add_neighbors "$N1_API" "$N2_IP" "$N3_IP"
add_neighbors "$N2_API" "$N1_IP" "$N3_IP"
add_neighbors "$N3_API" "$N1_IP" "$N2_IP"

start=$SECONDS
while :; do
  c1=$(connected_count "$N1_API")
  c2=$(connected_count "$N2_API")
  c3=$(connected_count "$N3_API")
  echo "connected neighbors -> node1:$c1 node2:$c2 node3:$c3"
  if [ "$c1" -eq 2 ] && [ "$c2" -eq 2 ] && [ "$c3" -eq 2 ]; then
    echo "OK: all 3 nodes are fully connected"
    exit 0
  fi
  if [ $((SECONDS - start)) -ge "$CONNECT_WAIT" ]; then
    break
  fi
  sleep "$CONNECT_POLL"
done

echo "ERROR: not fully connected after ${CONNECT_WAIT}s (slow start? try CONNECT_WAIT=300)."
echo "Check: docker logs <node> | grep -i -E 'handshak|drop|MWM|coordinator'"
exit 1
