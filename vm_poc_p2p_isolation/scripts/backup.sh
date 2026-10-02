#!/bin/bash

# Set variables (modify according to the actual path.)
BACKUP_DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="backup_house_A_${BACKUP_DATE}"
SECRET_KEY="${BACKUP_SECRET_KEY:?請先執行 export BACKUP_SECRET_KEY=你的密碼}"  # AES-256 Encrypted password
HORNET_DATA_PATH="/home/iota/iota-private/one-command-tangle"  #HORNET Database path

echo "=== Start the backup job [$BACKUP_DATE] ==="

mkdir -p /tmp/${BACKUP_DIR}   # Create a temporary work folder
echo "1. Copy HORNET ledger data and files"
cp -r ${HORNET_DATA_PATH}/db /tmp/${BACKUP_DIR}/
cp -r ${HORNET_DATA_PATH}/config /tmp/${BACKUP_DIR}/
echo "2. Package and encrypt using AES-256"
tar -czf - -C /tmp/${BACKUP_DIR} . | openssl enc -aes-256-cbc -pbkdf2 -k ${SECRET_KEY} -out /tmp/${BACKUP_DIR}.enc

# Call the script or use the curl API to upload to the cloud server
curl -X POST -F "file=@/tmp/${BACKUP_DIR}.enc" https://sv1.alexc.one/api/v1/backups/upload
# Clean up temporary unencrypted files
rm -rf /tmp/${BACKUP_DIR} /tmp/${BACKUP_DIR}.enc

echo "=== Backup successful. The encrypted backup file has been stored in /tmp/${BACKUP_DIR}.enc ==="
