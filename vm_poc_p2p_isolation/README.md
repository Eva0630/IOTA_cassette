> **本資料夾說明**：這是在獨立VM環境上，從零重新搭建三節點私有Tangle並完整驗證的紀錄，
> 涵蓋P2P連線除錯（MWM/coordinator address對齊問題排除）、Coordinator修復、
> 跨屋隔離邏輯驗證（UC5.3）與Admin存取自動留痕機制。
>
> 與 `uc5_4/` 資料夾內容的關係：`uc5_4/audit_chain_utils.py` 等三個同名檔案為先前較早期的
> 探索版本；本資料夾內同名檔案為本次在VM上重新完整驗證、功能更完整的版本
>（補上了雜湊化address命名規則、三節點查詢一致性比對、Admin存取行為自動上鏈等機制），
> 建議以本資料夾內容為準。

---

# IOTA 私有 Tangle 多節點跨屋隔離 POC

## 架構
- `docker/one-command-tangle/`：主節點(含Coordinator)設定
- `docker/multi-nodes/`：第二、三節點設定
- `scripts/`：稽核事件上鏈、跨屋隔離驗證、備份還原腳本

## 部署步驟
0. 前置條件：Compass 需要 `layers/`（預先建好的 Merkle tree），**它不是 `-bootstrap` 產生的，也不在本 repo 中**。
   請 clone 上游專案取得：`git clone https://github.com/iota-community/one-command-tangle.git`，
   再把其中的 `layers/` 整個複製到 `docker/one-command-tangle/layers/`（約 170MB，不要 commit）。
1. 進入 `docker/one-command-tangle/`，執行 `cp .env.example .env`，設定 `COMPASS_SEED`：
   - `.env.example` 只放佔位字串（不是合法 seed，Compass 會直接失敗），不再附上游公開的預設 seed。
   - 隨機 seed：`python3 gen_seed.py`（81 tryte，用 `secrets`）。**但 seed 與 `layers/` 共同決定
     coordinator address**：用新 seed 就必須用同一個 seed 重算 `layers/`，並把兩個 compose 檔的
     `--testnet-coordinator` 改成新的位址，等於一條新鏈。
   - 若只是本機測試、直接沿用上游 `layers/` 與 compose 內寫死的 coordinator address，
     seed 必須用上游 one-command-tangle `.env` 的預設值（公開、不安全，只能用在內網測試）。
   - **已在運作的鏈（例如 Pi）不要改 seed**，除非要用 `pi_ops/reset_chain.sh` 重建整條鏈。
2. **第一次啟動**前，把 `.env` 的 `EXTRA_COMPASS_FLAGS` 改成 `"-bootstrap"`，然後執行 `docker compose up -d`。
3. 確認 `latestMilestoneIndex` 持續增加後，把 `EXTRA_COMPASS_FLAGS` 改回 `""`，之後都不要再用 `-bootstrap`，否則出現 `Network already bootstrapped`。
4. 啟動第二、三節點：`cd ../multi-nodes && docker compose up -d`
5. 手動設定三節點互為 neighbor（每次重啟後都要重做）。
   遇到問題請參考 [TROUBLESHOOTING.md](TROUBLESHOOTING.md)。

### 啟動較慢的環境（QEMU / Raspberry Pi）調整等待時間

`docker/setup_neighbors.sh` 預設各等待 60 秒：先等每個節點的 API 起來，再等三節點互連。
在原生 x86 的 VM 上這樣就夠；若在 QEMU 模擬（例如 Raspberry Pi 5）下，IRI 啟動可能要好幾分鐘，
請用環境變數調大等待時間：

| 變數 | 說明 | 預設 |
|---|---|---|
| `READY_WAIT` | 每個節點等 API 回應的秒數 | 60 |
| `CONNECT_WAIT` | 加入 neighbor 後，等三節點互連的秒數 | 60 |
| `WAIT_SECONDS` | 一次同時設定上面兩者（個別變數優先） | （未設定） |

```bash
cd docker
# 原生 VM：照舊
./setup_neighbors.sh

# Pi / QEMU
READY_WAIT=600 CONNECT_WAIT=300 ./setup_neighbors.sh
# 或
WAIT_SECONDS=600 ./setup_neighbors.sh
```

- 變數必須是整數秒，否則腳本會直接報錯結束（結束碼 2）。
- 逾時會顯示實際等了幾秒，並提示調大哪個變數；互連失敗時請再檢查
  `docker logs <node> | grep -i -E 'handshak|drop|MWM|coordinator'`。
- 注意：Pi 上若是 `docker compose` v2，容器名稱是連字號；`scripts/restore.sh` 需用
  `CONTAINER_NAME`、`COMPASS_CONTAINER` 環境變數覆蓋。
- 注意：Pi 5 預設 16K page，x86 模擬需要 4K page（`getconf PAGESIZE` 應為 4096；
  否則在 `/boot/firmware/config.txt` 加 `kernel=kernel8.img` 後重開機）。

## 已知限制
- Coordinator 已修復可正常發送 milestone，但demo腳本因繞開PyOTA/pysha3相依問題，
  手動構造交易格式時bundle hash未真正計算，故測試交易無法進入confirmed狀態，
  僅能以「多節點資料一致性」作為簡化確認判準。
- 加密已實作 (AES-256-GCM，每戶金鑰由主金鑰衍生)。加密啟用之前上鏈的紀錄無法刪改，仍為明文，查詢時會標記 [LEGACY-PLAINTEXT]。
- 使用假的使用者字典模擬登入，尚未串接真實認證系統。

## 核心驗證腳本
- `scripts/send_audit_event.py`：上鏈稽核事件
- `scripts/audit_isolation_test.py`：驗證跨屋隔離(resident只能查自己家/admin可查全部且自動留痕)

## 加密金鑰設定
腳本需要環境變數 `AUDIT_MASTER_KEY`（64 個十六進位字元）才能加解密。

    openssl rand -hex 32 > ~/.audit_master_key && chmod 600 ~/.audit_master_key
    export AUDIT_MASTER_KEY=$(cat ~/.audit_master_key)

- 金鑰不可進版控，請另外備份；遺失後所有加密紀錄將永久無法解密。
- 測試：`cd scripts && python3 test_encryption.py`

## Ledger Worker（待上鏈事件存證）
`scripts/ledger_worker.py` 將 IOTA_API 的 `ledger_events(PENDING)` 以「雜湊存證」方式上鏈：
鏈上只放 event_id + payload_hash（加密後），不放業務資料。

- 送出前先查鏈，避免重複送出；三個節點回傳同一筆存證交易才標記 CONFIRMED。
- `confirmation_method = MULTINODE_CONSISTENCY`：不是 milestone 確認（已知限制）。
- 目前只支援 `--mock` 模式；待 IOTA_API 的 claim/confirm/fail 端點完成後補上 HTTP 版。
- 測試：`cd scripts && python3 test_ledger_worker.py`
