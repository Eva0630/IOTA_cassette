#!/bin/bash

# Set variables (modify according to the actual path.)
BACKUP_DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="backup_house_A_${BACKUP_DATE}"
SECRET_KEY="${BACKUP_SECRET_KEY:?請先執行 export BACKUP_SECRET_KEY=你的密碼}"  # AES-256 Encrypted password
HORNET_DATA_PATH="${HORNET_DATA_PATH:-/home/iota/iota-private/one-command-tangle}" # Tangle data path (can be overridden by env var)
UPLOAD_URL="${UPLOAD_URL:-https://sv1.alexc.one/api/v1/backups/upload}"
LOCAL_KEEP_DIR="${LOCAL_KEEP_DIR:-$HOME/backups}"

echo "=== Start the backup job [$BACKUP_DATE] ==="

# 0. Refuse to run if any required folder is missing (a backup without state/layers cannot restore the Coordinator)
for d in db config state layers; do
    if [ ! -d "${HORNET_DATA_PATH}/${d}" ]; then
        echo "Error: ${HORNET_DATA_PATH}/${d} not found. Nothing was backed up."
        exit 1
    fi
done

mkdir -p /tmp/${BACKUP_DIR}   # Create a temporary work folder
echo "1. Copy HORNET ledger data and files"
for d in db config state layers; do
    if ! cp -r ${HORNET_DATA_PATH}/${d} /tmp/${BACKUP_DIR}/; then
        echo "Error: failed to copy ${d}. Backup aborted."
        rm -rf /tmp/${BACKUP_DIR}
        exit 1
    fi
done

echo "2. Package and encrypt using AES-256"
if ! tar -czf - -C /tmp/${BACKUP_DIR} . | openssl enc -aes-256-cbc -pbkdf2 -k ${SECRET_KEY} -out /tmp/${BACKUP_DIR}.enc; then
    echo "Error: packaging/encryption failed. Backup aborted."
    rm -rf /tmp/${BACKUP_DIR} /tmp/${BACKUP_DIR}.enc
    exit 1
fi
rm -rf /tmp/${BACKUP_DIR}     # remove the unencrypted copy right away

# 3. Upload to the cloud server. Keep the local encrypted file unless the upload succeeded.
if curl -fsS -X POST -F "file=@/tmp/${BACKUP_DIR}.enc" "${UPLOAD_URL}"; then
    rm -f /tmp/${BACKUP_DIR}.enc
    echo "=== Backup successful and uploaded: ${BACKUP_DIR}.enc ==="
else
    mkdir -p "${LOCAL_KEEP_DIR}"
    mv /tmp/${BACKUP_DIR}.enc "${LOCAL_KEEP_DIR}/"
    echo "=== Upload FAILED. The encrypted backup is kept at ${LOCAL_KEEP_DIR}/${BACKUP_DIR}.enc ==="
    exit 2
fi
