# UC4.5 同步緊急實體覆寫紀錄

## 基本資訊

| 項目 | 內容 |
|---|---|
| UC 編號 | `UC4.5` |
| Ledger Event | `EMERGENCY_PHYSICAL_OVERWRITE` |
| 建議 API 檔名 | `sync_physical_overwrite.py` |
| 建議 Endpoint | `POST /cgi-bin/sync_physical_overwrite.py` |
| 目前狀態 | 尚需建立 Gateway 離線暫存與 Server 補發 API |

## 目的

設備在無法即時連網時記錄緊急實體覆寫，先交由 Gateway 本地暫存；恢復連線後補發至 Server 並上鏈。

## 角色與觸發時機

**主要角色：** ESP32／Gateway。實體操作者可能未知。

**建立上鏈事件的時機：** Server 驗證 Gateway 簽章、設備歸屬、事件唯一性與狀態變化後。

## 相關資料表

- `建議新增 physical_override_events`
- `devices`
- `audit_logs`
- `ledger_events`

## 標準上鏈 JSON

```json
{
  "schema_version": "1.0",
  "uc_id": "UC4.5",
  "event_id": "UUID",
  "event_type": "EMERGENCY_PHYSICAL_OVERWRITE",
  "is_overwrite": true,
  "family_id": 12,
  "gateway_id": "GW_001",
  "device_id": "ESP32_LOCK_001",
  "source": "GATEWAY_OFFLINE_CACHE",
  "timestamp": "2026-07-28T19:37:00+08:00",
  "received_at": "2026-07-28T20:15:04+08:00",
  "actor": {
    "actor_type": "PHYSICAL_OPERATOR",
    "actor_id_hash": null,
    "actor_role": "UNKNOWN"
  },
  "payload": {
    "operation": {
      "action": "EMERGENCY_UNLOCK",
      "trigger_source": "PHYSICAL_INTERFACE",
      "trigger_method": "MECHANICAL_OVERRIDE",
      "reason_code": "EMERGENCY_PHYSICAL_ACCESS"
    },
    "device_state_change": {
      "previous_state": "LOCKED",
      "new_state": "UNLOCKED"
    },
    "offline_context": {
      "network_available_at_event": false,
      "cached_locally": true,
      "cache_storage": "GATEWAY_LOCAL_DATABASE",
      "local_sequence": 128,
      "cached_at": "2026-07-28T19:37:01+08:00"
    },
    "replay_context": {
      "is_replayed": true,
      "replayed_at": "2026-07-28T20:15:03+08:00",
      "replay_attempt": 1,
      "idempotency_key": "GW_001-ESP32_LOCK_001-128"
    },
    "device_evidence": {
      "sensor_event_hash": "sha256:SENSOR_EVENT_HASH",
      "device_log_hash": "sha256:DEVICE_LOG_HASH"
    }
  },
  "integrity": {
    "hash_algorithm": "SHA-256",
    "payload_hash": "sha256:PAYLOAD_HASH",
    "signature_algorithm": "ECDSA_P256_SHA256",
    "signer_type": "GATEWAY",
    "signer_key_id": "GW_001_KEY_01",
    "signature": "base64:GATEWAY_SIGNATURE"
  }
}
```

## 必要驗證

1. 必須同時符合 `event_type=EMERGENCY_PHYSICAL_OVERWRITE` 與 `is_overwrite=true`，但這兩個欄位本身不足以證明事件可信。
2. 驗證 Gateway 簽章及 signer_key_id。
3. 驗證 device_id 屬於 gateway_id，gateway_id 屬於 family_id。
4. 以 `event_id` 與 `idempotency_key` 防止重複補發。
5. `timestamp` 是事件發生時間；`received_at` 是 Server 收到時間；`confirmed_at` 是上鏈確認時間，三者不可混用。
6. `local_sequence` 不可重複；若異常倒退或跳號，需標記待人工檢查。

## API 與區塊鏈組員分工

### Server API 負責

- 驗證請求、操作者、場域及資源歸屬。
- 完成業務資料更新。
- 建立 `audit_logs`。
- 呼叫 `enqueue_ledger_event()`，建立 `EMERGENCY_PHYSICAL_OVERWRITE` 事件。
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
    "event_type": "EMERGENCY_PHYSICAL_OVERWRITE"
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

- [ ] 斷網時 Gateway 可保存事件，恢復後可補發。
- [ ] Server 重複收到相同事件只處理一次。
- [ ] 設備目前實體狀態依補發資料更新。
- [ ] Ledger Event 保留實際事件時間，而非用收到或上鏈時間覆蓋。

## 共通安全規則

1. 不得將明文密碼、Session Key、訪客明文 Token、私鑰或完整個資寫入區塊鏈。
2. 使用者識別資料原則上使用 SHA-256 雜湊後上鏈；雜湊前可由 Server 加入系統端 salt 或使用 HMAC。
3. `payload_hash` 必須由 Canonical JSON 計算，固定 UTF-8、欄位排序及緊湊分隔符。
4. `event_id` 必須唯一，並在 `ledger_events.event_id` 建立 UNIQUE constraint。
5. Gateway 或設備補發事件必須驗證簽章，不得只信任 `is_overwrite=true` 或其他 Client 自填欄位。
6. 所有時間使用 ISO 8601，建議保留 `+08:00` 或統一轉為 UTC 後以 `Z` 表示。
