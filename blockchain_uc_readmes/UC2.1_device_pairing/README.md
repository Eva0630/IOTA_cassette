# UC2.1 裝置註冊與安全配對

## 基本資訊

| 項目 | 內容 |
|---|---|
| UC 編號 | `UC2.1` |
| Ledger Event | `DEVICE_REGISTERED_AND_PAIRED` |
| 建議 API 檔名 | `device_pair.py` |
| 建議 Endpoint | `POST /cgi-bin/device_pair.py` |
| 目前狀態 | 已有 `device_pair.py`，需接入 `ledger_events` |

## 目的

完成 Gateway 與 ESP32 的 ECDH 安全配對，保存裝置初始狀態與配對存證。

## 角色與觸發時機

**主要角色：** Admin。Gateway 為實際執行 ECDH 的可信節點。

**建立上鏈事件的時機：** ECDH、HKDF、裝置寫入 `devices` 及配對狀態更新成功後。

## 相關資料表

- `devices`
- `audit_logs`
- `ledger_events`

## 標準上鏈 JSON

```json
{
  "schema_version": "1.0",
  "uc_id": "UC2.1",
  "event_id": "UUID",
  "event_type": "DEVICE_REGISTERED_AND_PAIRED",
  "family_id": 12,
  "gateway_id": "GW_001",
  "device_id": "ESP32_LOCK_001",
  "source": "GATEWAY",
  "timestamp": "2026-07-28T10:15:30+08:00",
  "actor": {
    "actor_type": "USER",
    "actor_id_hash": "sha256:ADMIN_ID_HASH",
    "actor_role": "ADMIN"
  },
  "payload": {
    "device_type": "SMART_LOCK",
    "device_name_hash": "sha256:DEVICE_NAME_HASH",
    "initial_status": {
      "pairing_status": "PAIRED",
      "operational_status": "ACTIVE",
      "physical_state": "LOCKED"
    },
    "security_pairing": {
      "protocol": "ECDH",
      "curve": "SECP256R1",
      "device_public_key_hash": "sha256:DEVICE_PUBLIC_KEY_HASH",
      "gateway_public_key_hash": "sha256:GATEWAY_PUBLIC_KEY_HASH",
      "session_key_hash": "sha256:SESSION_KEY_HASH",
      "pairing_result": "SUCCESS"
    },
    "paired_at": "2026-07-28T10:15:30+08:00",
    "created_by_hash": "sha256:ADMIN_ID_HASH"
  }
}
```

## 必要驗證

1. Admin 必須屬於 `family_id` 且具有裝置配對權限。
2. `device_id` 不得已被其他場域配對。
3. 已除役裝置不得直接重新配對，必須經過重新啟用或重新註冊流程。
4. 不得保存或上鏈明文 Session Key。
5. 正式環境不可使用 mock ESP32 public key。

## API 與區塊鏈組員分工

### Server API 負責

- 驗證請求、操作者、場域及資源歸屬。
- 完成業務資料更新。
- 建立 `audit_logs`。
- 呼叫 `enqueue_ledger_event()`，建立 `DEVICE_REGISTERED_AND_PAIRED` 事件。
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
    "event_type": "DEVICE_REGISTERED_AND_PAIRED"
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

- [ ] 配對成功後 `devices.pairing_status=paired`。
- [ ] `session_key_hash` 已保存，但資料庫及回應中沒有 Session Key 明文。
- [ ] `audit_logs` 與 `ledger_events` 各有一筆對應事件。

## 共通安全規則

1. 不得將明文密碼、Session Key、訪客明文 Token、私鑰或完整個資寫入區塊鏈。
2. 使用者識別資料原則上使用 SHA-256 雜湊後上鏈；雜湊前可由 Server 加入系統端 salt 或使用 HMAC。
3. `payload_hash` 必須由 Canonical JSON 計算，固定 UTF-8、欄位排序及緊湊分隔符。
4. `event_id` 必須唯一，並在 `ledger_events.event_id` 建立 UNIQUE constraint。
5. Gateway 或設備補發事件必須驗證簽章，不得只信任 `is_overwrite=true` 或其他 Client 自填欄位。
6. 所有時間使用 ISO 8601，建議保留 `+08:00` 或統一轉為 UTC 後以 `Z` 表示。
