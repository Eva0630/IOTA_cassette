# IOTA 私有 Tangle 多節點跨屋隔離 POC

## 架構
- `docker/one-command-tangle/`：主節點(含Coordinator)設定
- `docker/multi-nodes/`：第二、三節點設定
- `scripts/`：稽核事件上鏈、跨屋隔離驗證、備份還原腳本

## 部署步驟
1. 複製 `docker/one-command-tangle/.env.example` 為 `.env`，填入真實的 COMPASS_SEED
2. 啟動主節點：`cd docker/one-command-tangle && docker compose up -d`
3. 啟動第二、三節點：`cd docker/multi-nodes && docker compose up -d`
4. 參考本次除錯紀錄手動設定三節點互為neighbor（MWM、coordinator address需一致）

## 已知限制
- Coordinator 已修復可正常發送 milestone，但demo腳本因繞開PyOTA/pysha3相依問題，
  手動構造交易格式時bundle hash未真正計算，故測試交易無法進入confirmed狀態，
  僅能以「多節點資料一致性」作為簡化確認判準。
- 加密機制為pass-through插槽，尚未實作真正的加密。
- 使用假的使用者字典模擬登入，尚未串接真實認證系統。

## 核心驗證腳本
- `scripts/send_audit_event.py`：上鏈稽核事件
- `scripts/audit_isolation_test.py`：驗證跨屋隔離(resident只能查自己家/admin可查全部且自動留痕)
