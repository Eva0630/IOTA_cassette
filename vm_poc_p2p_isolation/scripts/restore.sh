#!/bin/bash

#1. Check parameters: Must specify which '.enc' backup file to restore
if [ -z "$1" ]; then
    echo "Error: Please specify the path to the encrypted backup file to restore!"
    echo "Example: ./restore.sh /tmp/backup_house_A_20260807_150031.enc"
    exit 1
fi

ENC_FILE="$1"
SECRET_KEY="${BACKUP_SECRET_KEY:?請先執行 export BACKUP_SECRET_KEY=你的密碼}"  # Must be exactly the same as "backup.sh"'s password
TANGLE_PATH="/home/iota/iota-private/one-command-tangle"
TEMP_RESTORE_DIR="/tmp/restore_temp"
CONTAINER_NAME="one-command-tangle_iri_1"  # Docker container name

# Check if the backup file exists
if [ ! -f "${ENC_FILE}" ]; then
    echo "Error: Backup file ${ENC_FILE} not found"
    exit 1
fi

echo "=== Start the restore operation ==="
echo "Expected file to be restored: ${ENC_FILE}"

#2. Pause the running Docker container
echo "Stopping the HORNET node container ..."
sudo docker stop ${CONTAINER_NAME} 2>/dev/null || true

#3. Create a temporary folder for decryption
mkdir -p ${TEMP_RESTORE_DIR}

#4. Perform AES-256 decryption & decompression
echo "Performing AES-256 decryption & decompression ..."
openssl enc -d -aes-256-cbc -pbkdf2 -k ${SECRET_KEY} -in ${ENC_FILE} | tar -xzf - -C ${TEMP_RESTORE_DIR}

#5. Clear corrupt/old data and overwrite with backup data
echo "Overwiting and restoring Tangle ledger DB & Config ..."
sudo rm -rf ${TANGLE_PATH}/db ${TANGLE_PATH}/config
sudo cp -r ${TEMP_RESTORE_DIR}/db ${TANGLE_PATH}/
sudo cp -r ${TEMP_RESTORE_DIR}/config ${TANGLE_PATH}/

#6. Clean up temporary decryption folder
rm -rf ${TEMP_RESTORE_DIR}

#7. Restart Docker container
echo "Restarting HORNET node container ..."
sudo docker start ${CONTAINER_NAME} 2>/dev/null || true

echo "=== Restoration successful! Ledger data has been fully recovered and reconnected ==="

