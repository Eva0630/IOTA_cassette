# 除錯紀錄與部署注意事項

本文件整理三節點私有 Tangle 在 VM 上搭建時遇到的問題與解法。
部署到新環境時，建議先對照這份清單。

## 0. 先決條件：Compass 需要 layers/（Merkle tree）

- `layers/` 由上游 one-command-tangle 專案預先附帶（深度 20），**不是 `-bootstrap` 產生的**。
- 缺少 layers 時，Compass 會出現 `IndexOutOfBoundsException: Index: 0, Size: 0`。
- 取得方式：clone 上游專案，或從已運作的機器複製 `layers/`（約 170MB，不要 commit 進 git）。
- IRI 的 `--testnet-coordinator` 位址是由預設 seed 加上這份 layers 推導出來的，兩者必須對應。
- `COMPASS_SEED` 使用上游公開的預設值（見 `.env.example`），僅限本機測試。

## 1. Compass 啟動就崩潰：Network already bootstrapped

- 原因：`.env` 裡 `EXTRA_COMPASS_FLAGS="-bootstrap"`，但網路已經 bootstrap 過。
- 解法：改成 `EXTRA_COMPASS_FLAGS=""`，Compass 會讀 `state/statefile` 接續發 milestone。
- `-bootstrap` 只能在第一次啟動使用。

## 2. node2/node3 無法使用 getNeighbors / addNeighbors

- 原因：IRI image 預設把這些指令列在 `DOCKER_IRI_REMOTE_LIMIT_API` 的禁止清單。
- 解法：啟動參數加上 `--remote-limit-api ""`。
- 注意：這會開放所有遠端指令，只適合內網測試。

## 3. neighbor 加了但 connected: false

查看 log 中 `dropping handshaked connection` 的原因，常見兩種：

| log 訊息 | 原因 | 解法 |
|---|---|---|
| `different MWM (X instead of Y)` | 三節點 `--mwm` 不一致 | 全部統一（本專案為 9） |
| `different coordinator address` | 沒帶 `--testnet-coordinator` 等參數 | 三節點的 coordinator 相關參數與 snapshot 必須完全一致 |

另一個原因是 `Connection timed out`：容器 IP 變了，舊的 neighbor 位址已失效。
compose 裡已用 `ipv4_address` 固定 IP。

## 4. 資料庫掛載路徑

- testnet 模式下，IRI 的資料庫在容器內的 `/iri/data/testnetdb`。
- volume 必須掛載 `/iri/data`，掛成 `/app/mainnetdb` 會造成資料沒有落地。

## 5. 新節點同步卡在 milestone 0

- 現象：`latestSolidSubtangleMilestoneIndex` 長時間為 0，log 裡 `toRequest` 數字不變。
- 原因：IRI 的被動式請求機制無法追上大量落後的 milestone。
- 解法：停止所有節點，把已同步節點的 `db/` 整個複製（`cp -a`）給新節點後重啟。

## 6. 每次重啟後 neighbor 會消失

- neighbor 名單不會持久化，重啟或 `docker compose down/up` 後要重新執行 `addNeighbors`。
- 加完等約 10 秒，再用 `getNeighbors` 確認三個節點都是 `connected: true`。

## 7. 手動組交易的限制（已知限制）

- PyOTA 依賴的 `pysha3` 無法在 Python 3.11 編譯，因此改用 HTTP API 手動組交易。
- 交易的 `trunk`/`branch` 必須填入 `getTransactionsToApprove` 回傳的真實 tip。
- `bundleHash` 未真正計算（需要 Kerl 雜湊），所以測試交易可以被三節點查詢到，
  但不會被 milestone 確認，永遠是 pending。
- 目前以「三節點查詢結果一致」作為簡化的確認判準。

## 8. 備份與還原

- `backup.sh` 備份 `db`、`config`、`state`、`layers`，缺少 `state` 或 `layers` 就無法還原 Coordinator。
- `restore.sh` 會先解密驗證，成功才停容器；舊資料改名為 `*.old_時間戳` 保留，確認無誤後再手動刪除。
- 兩個腳本都需要先 `export BACKUP_SECRET_KEY=...`。
- Coordinator 同一時間只能有一份在運作，不要讓兩台機器對同一條鏈各跑一個。

## 9. 節點被系統殺掉：Exited (137) / OOMKilled

- 判斷：`docker inspect <容器> --format '{{.State.OOMKilled}}'` 為 `true`。
- 原因：IRI 預設 `JAVA_MAX_MEMORY=4G`，三個節點加起來超過主機記憶體。
- 解法：在 compose 的 `environment` 設 `JAVA_MAX_MEMORY=1500M`、`JAVA_MIN_MEMORY=512M`（私有 testnet 流量小，足夠）。
- 注意：拼字是 `environment`，拼錯 compose 不會生效。
- Compass 因為連不上 IRI 會跟著崩潰，先啟動 IRI，確認 `getNodeInfo` 有回應，再啟動 Compass，最後執行 `setup_neighbors.sh`。

## 10. docker compose 與 docker-compose

- 新版 Docker 是 `docker compose`（空格），舊版是 `docker-compose`（連字號）。
- 出現 `'compose' is not a docker command` 時，改用 `docker-compose`。
- 重啟後 neighbor 會消失，執行 `docker/setup_neighbors.sh` 重新建立並驗證。
