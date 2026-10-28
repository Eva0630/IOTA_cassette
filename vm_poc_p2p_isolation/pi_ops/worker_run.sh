#!/bin/bash
set -euo pipefail
set -a; . /mnt/usb/IOTA_API/.ledger.env; set +a
export LEDGER_API_URL=http://127.0.0.1:8091
export LEDGER_WORKER_ID=pi5-manual
export AUDIT_MASTER_KEY=$(cat /home/iota/.audit_master_key)
cd /mnt/usb/IOTA_cassette/vm_poc_p2p_isolation/scripts
exec python3 http_bridge.py "$@"
