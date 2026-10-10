#!/bin/bash
set -o pipefail

#1. Check parameters: Must specify which '.enc' backup file to restore
if [ -z "$1" ]; then
    echo "Error: Please specify the path to the encrypted backup file to restore!"
    echo "Example: ./restore.sh /tmp/backup_house_A_20260807_150031.enc"
    exit 1
fi

ENC_FILE="$1"
SECRET_KEY="${BACKUP_SECRET_KEY:?請先執行 export BACKUP_SECRET_KEY=你的密碼}"  # Must be the same as backup.sh
TANGLE_PATH="${TANGLE_PATH:-/home/iota/iota-private/one-command-tangle}"
TEMP_RESTORE_DIR="/tmp/restore_temp"
CONTAINER_NAME="${CONTAINER_NAME:-one-command-tangle_iri_1}"
COMPASS_CONTAINER="${COMPASS_CONTAINER:-one-command-tangle_compass_1}"
OLD_SUFFIX=".old_$(date +%Y%m%d_%H%M%S)"

if [ ! -f "${ENC_FILE}" ]; then
    echo "Error: Backup file ${ENC_FILE} not found"
    exit 1
fi

echo "=== Start the restore operation ==="
echo "Backup file: ${ENC_FILE}"

#2. Decrypt FIRST and verify, so a bad backup never touches the live data
rm -rf "${TEMP_RESTORE_DIR}"
mkdir -p "${TEMP_RESTORE_DIR}"
echo "Decrypting & extracting ..."
if ! openssl enc -d -aes-256-cbc -pbkdf2 -k "${SECRET_KEY}" -in "${ENC_FILE}" | tar -xzf - -C "${TEMP_RESTORE_DIR}"; then
    echo "Error: decryption/extraction failed (wrong password or corrupted file). Nothing was changed."
    rm -rf "${TEMP_RESTORE_DIR}"
    exit 1
fi
if [ ! -d "${TEMP_RESTORE_DIR}/db" ]; then
    echo "Error: backup does not contain a db folder. Nothing was changed."
    rm -rf "${TEMP_RESTORE_DIR}"
    exit 1
fi

#3. Stop containers (only after the backup is confirmed usable)
echo "Stopping containers ..."
sudo docker stop "${COMPASS_CONTAINER}" 2>/dev/null || true
sudo docker stop "${CONTAINER_NAME}" 2>/dev/null || true

#4. Move old data aside (not deleted) and restore from backup
for d in db config state layers; do
    if [ -d "${TEMP_RESTORE_DIR}/${d}" ]; then
        if [ -e "${TANGLE_PATH}/${d}" ]; then
            sudo mv "${TANGLE_PATH}/${d}" "${TANGLE_PATH}/${d}${OLD_SUFFIX}"
        fi
        sudo cp -r "${TEMP_RESTORE_DIR}/${d}" "${TANGLE_PATH}/"
        echo "  restored: ${d}"
    else
        echo "  skipped (not in this backup): ${d}"
    fi
done

#5. Clean up temp folder
rm -rf "${TEMP_RESTORE_DIR}"

#6. Restart containers
echo "Restarting containers ..."
sudo docker start "${CONTAINER_NAME}" 2>/dev/null || true
sudo docker start "${COMPASS_CONTAINER}" 2>/dev/null || true

echo "=== Restore finished. Old data kept as *${OLD_SUFFIX} in ${TANGLE_PATH} (delete manually once verified) ==="
