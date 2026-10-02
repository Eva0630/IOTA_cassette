# 上鏈 UC API 規格文件

本資料夾包含目前確認需要上鏈的 8 個使用案例。每個 UC 皆有獨立 `README.md`，可作為 API、資料庫與區塊鏈組員分工的實作依據。

## 文件清單

| UC | 使用案例 | Ledger event_type | 目前狀態 |
|---|---|---|---|
| [UC1.3](UC1.3_gateway_initialization/README.md) | 閘道器初始化與屋主綁定 | `SITE_GENESIS_CREATED` | 尚需建立正式 API |
| [UC2.1](UC2.1_device_pairing/README.md) | 裝置註冊與安全配對 | `DEVICE_REGISTERED_AND_PAIRED` | 已有 `device_pair.py`，需接入 `ledger_events` |
| [UC2.3](UC2.3_device_decommission/README.md) | 終端設備除役與安全解綁 | `DEVICE_DECOMMISSIONED` | 已有 `decommission_device.py`，需接入 `ledger_events` 並補正式憑證撤銷 |
| [UC3.3](UC3.3_member_revocation/README.md) | 移除成員與撤銷權限 | `MEMBER_PERMISSION_REVOKED` | 尚需建立正式 API；可與現有 `update_member_role.py` 整合 |
| [UC3.4](UC3.4_guest_token_issue/README.md) | 核發訪客臨時授權 | `GUEST_TOKEN_ISSUED` | 目前只有 `issue_guest_token_demo.py`，需升級為正式 API |
| [UC3.5](UC3.5_guest_token_revocation/README.md) | 撤銷訪客臨時令牌 | `GUEST_TOKEN_REVOKED` | 尚需建立正式 API |
| [UC4.4](UC4.4_security_anomaly/README.md) | 接收分權通知與異常推播 | `SECURITY_ANOMALY_RECORDED` | 尚需建立異常事件接收、分類與上鏈 API |
| [UC4.5](UC4.5_physical_overwrite_sync/README.md) | 同步緊急實體覆寫紀錄 | `EMERGENCY_PHYSICAL_OVERWRITE` | 尚需建立 Gateway 離線暫存與 Server 補發 API |

## 共用 Ledger Bridge API

區塊鏈組員的 Worker 建議只透過以下內部 API 交換資料：

| API | 用途 |
|---|---|
| `POST /internal/ledger/events/claim` | 領取待上鏈事件並取得處理租約 |
| `POST /internal/ledger/events/confirm` | 回報成功、交易參考值與確認時間 |
| `POST /internal/ledger/events/fail` | 回報失敗、是否可重試及錯誤代碼 |
| `POST /internal/ledger/events/status` | 查詢單一事件的上鏈狀態 |
| `GET /internal/ledger/health` | 查詢待處理、重試及死信數量 |

## 建議目錄

```text
api/
├── common/
│   ├── canonical_json.py
│   ├── ledger_auth.py
│   └── ledger_event_service.py
├── ledger/
│   ├── claim_ledger_events.py
│   ├── confirm_ledger_event.py
│   ├── fail_ledger_event.py
│   ├── get_ledger_event_status.py
│   └── ledger_health.py
├── database/
│   └── migration_add_ledger_events.sql
└── examples/
    └── mock_iota_worker.py
```

## Ledger 狀態

| 狀態 | 說明 |
|---|---|
| `PENDING` | 已建立事件，等待 Worker 領取 |
| `PROCESSING` | 已由 Worker claim，租約期間內不得被其他 Worker 重複處理 |
| `SUBMITTED` | 已送至 IOTA，等待確認 |
| `CONFIRMED` | 已取得鏈上確認及交易參考值 |
| `RETRY` | 暫時性失敗，等待下次重試 |
| `DEAD_LETTER` | 超過重試次數或不可重試，需人工處理 |

## 共通安全規則

1. 不得將明文密碼、Session Key、訪客明文 Token、私鑰或完整個資寫入區塊鏈。
2. 使用者識別資料原則上使用 SHA-256 雜湊後上鏈；雜湊前可由 Server 加入系統端 salt 或使用 HMAC。
3. `payload_hash` 必須由 Canonical JSON 計算，固定 UTF-8、欄位排序及緊湊分隔符。
4. `event_id` 必須唯一，並在 `ledger_events.event_id` 建立 UNIQUE constraint。
5. Gateway 或設備補發事件必須驗證簽章，不得只信任 `is_overwrite=true` 或其他 Client 自填欄位。
6. 所有時間使用 ISO 8601，建議保留 `+08:00` 或統一轉為 UTC 後以 `Z` 表示。
