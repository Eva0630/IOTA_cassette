# UC3.4 核發訪客臨時授權

## 基本資訊

| 項目 | 內容 |
|---|---|
| UC 編號 | `UC3.4` |
| Ledger Event | `GUEST_TOKEN_ISSUED` |
| 建議 API 檔名 | `issue_guest_token.py` |
| 建議 Endpoint | `POST /cgi-bin/issue_guest_token.py` |
| 目前狀態 | 目前只有 `issue_guest_token_demo.py`，需升級為正式 API |

## 目的

核發具有場域、設備、動作、有效時間與次數限制的短效訪客 Token。

## 角色與觸發時機

**主要角色：** Admin 或具有臨時授權核發權限的使用者。

**建立上鏈事件的時機：** 明文 Token 已產生一次、資料庫只保存 Token 雜湊，且授權範圍驗證成功後。

## 相關資料表

- `guest_tokens`
- `audit_logs`
- `ledger_events`

## 標準上鏈 JSON

```json
{
  "schema_version": "1.0",
  "uc_id": "UC3.4",
  "event_id": "UUID",
  "event_type": "GUEST_TOKEN_ISSUED",
  "family_id": 12,
  "gateway_id": "GW_001",
  "source": "SERVER",
  "timestamp": "2026-07-28T13:00:00+08:00",
  "actor": {
    "actor_type": "USER",
    "actor_id_hash": "sha256:ISSUER_ID_HASH",
    "actor_role": "ADMIN"
  },
  "payload": {
    "token_id": "GT_20260728_0001",
    "token_hash": "sha256:GUEST_TOKEN_HASH",
    "authorization_scope": [
      {
        "device_id": "ESP32_LOCK_001",
        "allowed_actions": [
          "UNLOCK"
        ]
      }
    ],
    "validity": {
      "valid_from": "2026-07-28T13:00:00+08:00",
      "expires_at": "2026-07-29T13:00:00+08:00"
    },
    "usage_limit": {
      "max_uses": 1,
      "initial_remaining_uses": 1
    },
    "issuer_id_hash": "sha256:ISSUER_ID_HASH",
    "token_status": "ACTIVE"
  }
}
```

## 必要驗證

1. 明文 Token 只允許在核發成功回應中顯示一次。
2. 資料庫與區塊鏈只能保存 `token_hash`。
3. `expires_at` 必須晚於 `valid_from`，且不可超過系統允許的最長期限。
4. `max_uses` 必須大於 0。
5. 授權動作必須存在於設備允許的 Action 白名單。

## API 與區塊鏈組員分工

### Server API 負責

- 驗證請求、操作者、場域及資源歸屬。
- 完成業務資料更新。
- 建立 `audit_logs`。
- 呼叫 `enqueue_ledger_event()`，建立 `GUEST_TOKEN_ISSUED` 事件。
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
    "event_type": "GUEST_TOKEN_ISSUED"
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

- [ ] 訪客能在期限與次數範圍內執行指定動作。
- [ ] 明文 Token 不出現在 `audit_logs`、`ledger_events` 或一般日誌。
- [ ] Token 雜湊、授權範圍、期限、次數與核發者均可稽核。

## 共通安全規則

1. 不得將明文密碼、Session Key、訪客明文 Token、私鑰或完整個資寫入區塊鏈。
2. 使用者識別資料原則上使用 SHA-256 雜湊後上鏈；雜湊前可由 Server 加入系統端 salt 或使用 HMAC。
3. `payload_hash` 必須由 Canonical JSON 計算，固定 UTF-8、欄位排序及緊湊分隔符。
4. `event_id` 必須唯一，並在 `ledger_events.event_id` 建立 UNIQUE constraint。
5. Gateway 或設備補發事件必須驗證簽章，不得只信任 `is_overwrite=true` 或其他 Client 自填欄位。
6. 所有時間使用 ISO 8601，建議保留 `+08:00` 或統一轉為 UTC 後以 `Z` 表示。
