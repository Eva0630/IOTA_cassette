#!/bin/bash
# setup_neighbors.sh
# Re-add neighbors for the 3-node private tangle and verify they are connected.
# IRI does not persist neighbors, so run this after every restart.

N1_API="${N1_API:-http://localhost:14265}"
N2_API="${N2_API:-http://localhost:14266}"
N3_API="${N3_API:-http://localhost:14267}"
N1_IP="${N1_IP:-172.28.0.1}"   # node1 uses host network -> reached via the bridge gateway
N2_IP="${N2_IP:-172.28.0.2}"
N3_IP="${N3_IP:-172.28.0.3}"
GOSSIP_PORT="${GOSSIP_PORT:-15600}"

api() {
  curl -s --max-time 5 -X POST "$1" \
    -H 'Content-Type: application/json' \
    -H 'X-IOTA-API-Version: 1' -d "$2"
}

wait_ready() {
  for _ in $(seq 1 30); do
    api "$1" '{"command":"getNodeInfo"}' | grep -q '"appName"' && return 0
    sleep 2
  done
  echo "ERROR: $1 is not responding"
  return 1
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

for _ in $(seq 1 12); do
  c1=$(connected_count "$N1_API")
  c2=$(connected_count "$N2_API")
  c3=$(connected_count "$N3_API")
  echo "connected neighbors -> node1:$c1 node2:$c2 node3:$c3"
  if [ "$c1" -eq 2 ] && [ "$c2" -eq 2 ] && [ "$c3" -eq 2 ]; then
    echo "OK: all 3 nodes are fully connected"
    exit 0
  fi
  sleep 5
done

echo "ERROR: not fully connected. Check: docker logs <node> | grep -i -E 'handshak|drop|MWM|coordinator'"
exit 1
