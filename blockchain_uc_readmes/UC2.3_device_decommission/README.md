# UC2.3 終端設備除役與安全解綁

## 基本資訊

| 項目 | 內容 |
|---|---|
| UC 編號 | `UC2.3` |
| Ledger Event | `DEVICE_DECOMMISSIONED` |
| 建議 API 檔名 | `decommission_device.py` |
| 建議 Endpoint | `POST /cgi-bin/decommission_device.py` |
| 目前狀態 | 已有 `decommission_device.py`，需接入 `ledger_events` 並補正式憑證撤銷 |

## 目的

停用設備、撤銷憑證與會話信任，保留不可否認的除役紀錄。

## 角色與觸發時機

**主要角色：** Admin。

**建立上鏈事件的時機：** 設備狀態改為除役、配對關係解除、Session Key 失效及憑證撤銷成功後。

## 相關資料表

- `devices`
- `建議新增 device_credentials 或 revocations`
- `audit_logs`
- `ledger_events`

## 標準上鏈 JSON

```json
{
  "schema_version": "1.0",
  "uc_id": "UC2.3",
  "event_id": "UUID",
  "event_type": "DEVICE_DECOMMISSIONED",
  "family_id": 12,
  "gateway_id": "GW_001",
  "device_id": "ESP32_LOCK_001",
  "source": "SERVER",
  "timestamp": "2026-07-28T11:00:00+08:00",
  "actor": {
    "actor_type": "USER",
    "actor_id_hash": "sha256:ADMIN_ID_HASH",
    "actor_role": "ADMIN"
  },
  "payload": {
    "status_change": {
      "previous_status": "ACTIVE",
      "new_status": "DECOMMISSIONED",
      "pairing_status": "UNPAIRED"
    },
    "credential_revocation": {
      "credential_id_hash": "sha256:CREDENTIAL_ID_HASH",
      "revocation_status": "REVOKED",
      "revoked_at": "2026-07-28T11:00:00+08:00"
    },
    "trust_chain_terminated": true,
    "reason": {
      "reason_code": "DEVICE_REPLACED",
      "reason_detail_hash": "sha256:REASON_DETAIL_HASH"
    },
    "operated_by_hash": "sha256:ADMIN_ID_HASH"
  }
}
```

## 必要驗證

1. 設備必須存在且屬於指定場域。
2. 操作者必須具有 Admin 權限。
3. 重複除役同一設備時回傳目前狀態，不得重複產生不同除役事件。
4. `session_key_hash` 必須清除或標記為失效。
5. 若有設備憑證表，必須先完成撤銷再建立 Ledger Event。

## API 與區塊鏈組員分工

### Server API 負責

- 驗證請求、操作者、場域及資源歸屬。
- 完成業務資料更新。
- 建立 `audit_logs`。
- 呼叫 `enqueue_ledger_event()`，建立 `DEVICE_DECOMMISSIONED` 事件。
- 回應業務操作結果及 `ledger_event_id`，不等待 IOTA 最終確認。

### Ledger Worker 負責

- 透過 claim API 取得事件。
- 重新計算並核對 `payload_hash`。
- 將必要事件資料或雜湊提交至 IOTA。
- 成功時回報交易參考值；失敗時回報錯誤與是否可重試。

## 建議成功回應

```json
{
  "status": "Success",
  "message": "Business operation completed and ledger event queued.",
  "data": {
    "ledger_event_id": "UUID",
    "ledger_status": "PENDING",
    "event_type": "DEVICE_DECOMMISSIONED"
  }
}
```

## 建議錯誤回應

```json
{
  "status": "Error",
  "code": "VALIDATION_OR_PERMISSION_ERROR",
  "message": "The request cannot be processed.",
  "detail": null
}
```

## 驗收條件

- [ ] 設備資料不被刪除，狀態改為除役。
- [ ] 裝置無法再接受正常控制。
- [ ] 除役原因、操作者雜湊及撤銷時間均存在於事件中。

## 共通安全規則

1. 不得將明文密碼、Session Key、訪客明文 Token、私鑰或完整個資寫入區塊鏈。
2. 使用者識別資料原則上使用 SHA-256 雜湊後上鏈；雜湊前可由 Server 加入系統端 salt 或使用 HMAC。
3. `payload_hash` 必須由 Canonical JSON 計算，固定 UTF-8、欄位排序及緊湊分隔符。
4. `event_id` 必須唯一，並在 `ledger_events.event_id` 建立 UNIQUE constraint。
5. Gateway 或設備補發事件必須驗證簽章，不得只信任 `is_overwrite=true` 或其他 Client 自填欄位。
6. 所有時間使用 ISO 8601，建議保留 `+08:00` 或統一轉為 UTC 後以 `Z` 表示。
