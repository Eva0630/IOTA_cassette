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
1. 進入 `docker/one-command-tangle/`，執行 `cp .env.example .env`。
   `COMPASS_SEED` 已是上游公開的預設值（僅限本機測試），不需要修改。
2. **第一次啟動**前，把 `.env` 的 `EXTRA_COMPASS_FLAGS` 改成 `"-bootstrap"`，然後執行 `docker compose up -d`。
3. 確認 `latestMilestoneIndex` 持續增加後，把 `EXTRA_COMPASS_FLAGS` 改回 `""`，之後都不要再用 `-bootstrap`，否則出現 `Network already bootstrapped`。
4. 啟動第二、三節點：`cd ../multi-nodes && docker compose up -d`
5. 手動設定三節點互為 neighbor（每次重啟後都要重做）。
   遇到問題請參考 [TROUBLESHOOTING.md](TROUBLESHOOTING.md)。

## 已知限制
- Coordinator 已修復可正常發送 milestone，但demo腳本因繞開PyOTA/pysha3相依問題，
  手動構造交易格式時bundle hash未真正計算，故測試交易無法進入confirmed狀態，
  僅能以「多節點資料一致性」作為簡化確認判準。
- 加密機制為pass-through插槽，尚未實作真正的加密。
- 使用假的使用者字典模擬登入，尚未串接真實認證系統。

## 核心驗證腳本
- `scripts/send_audit_event.py`：上鏈稽核事件
- `scripts/audit_isolation_test.py`：驗證跨屋隔離(resident只能查自己家/admin可查全部且自動留痕)
