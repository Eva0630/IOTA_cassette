#!/bin/bash
set -euo pipefail
export AUDIT_MASTER_KEY=$(cat /home/iota/.audit_master_key)
cd /mnt/usb/IOTA_cassette/vm_poc_p2p_isolation/scripts
exec python3 tamper_check.py "$@"
