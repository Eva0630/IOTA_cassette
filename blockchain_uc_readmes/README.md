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

區塊鏈組員的 Worker 只透過以下內部 API 交換資料。實作在 IOTA_API repo 的
`API/ledger_bridge/router.py`（FastAPI router，prefix `/ledger`，由 `API/gateway.py` 掛載）；
Worker 端實作是本 repo 的 `vm_poc_p2p_isolation/scripts/http_bridge.py`。

所有端點都需要 `Authorization: Bearer <LEDGER_WORKER_TOKEN>`（Server 端 token 至少 32 字元，否則回 503；錯誤 token 回 401）。

| API | Request body | 用途 |
|---|---|---|
| `GET /ledger/health` | — | 檢查 DB 連線與 migration，回傳 `{ok, protocol_version, claim_token_required, counts}`，`counts` 為各狀態事件數 |
| `POST /ledger/claim` | `worker_id`、`limit`（1–20，預設 1）、`lease_seconds`（15–3600，預設 300）、`preview`（預設 false） | 領取 `PENDING`、已到重試時間的 `RETRY`、租約已過期的 `PROCESSING`/`SUBMITTED` 事件並取得租約；每筆回傳 `claim_token`、`recovery_required`、`previous_status`、`ledger_reference` 等。`preview=true` 只預覽、不改狀態、不發 token |
| `POST /ledger/{event_id}/submitted` | `claim_token`、`ledger_reference` | 回報已送上鏈（→ `SUBMITTED`），記錄交易 hash |
| `POST /ledger/{event_id}/confirm` | `claim_token`、`ledger_reference`、`confirmation_method` | 回報已確認（→ `CONFIRMED`），記錄 `confirmed_at` 與確認方式 |
| `POST /ledger/{event_id}/fail` | `claim_token`、`error`（≤500 字）、`retryable` | 回報失敗（→ `RETRY`，指數退避；超過 5 次或不可重試 → `DEAD_LETTER`） |

規則：
- `submitted` / `confirm` / `fail` 都必須帶 claim 時拿到的 `claim_token`，且租約未過期、事件仍為 `PROCESSING`/`SUBMITTED`，否則回 409。
- `ledger_reference` 一旦記錄就不能換成別的交易（409）。
- 同一個 `claim_token` 重送完全相同的回報是冪等的（回傳上次結果）；內容不同則 409。
- 沒有單一事件狀態查詢端點；狀態查 `ledger_events` 資料表或看 `health` 的 `counts`。
- `confirmation_method`：Worker 以 milestone（`getInclusionStates`）確認時填 `MILESTONE`；
  等待逾時則退回 `MULTINODE_CONSISTENCY`（三節點讀到相同的存證交易）。

> 早期版本文件寫的 `/internal/ledger/events/*`（含 `status` 端點）沒有實作，以上表為準。

## 建議目錄（早期規劃，實際 API 實作見 IOTA_API `API/ledger_bridge/`）

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
