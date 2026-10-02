# UC3.3 移除成員與撤銷權限

## 基本資訊

| 項目 | 內容 |
|---|---|
| UC 編號 | `UC3.3` |
| Ledger Event | `MEMBER_PERMISSION_REVOKED` |
| 建議 API 檔名 | `remove_member.py` |
| 建議 Endpoint | `POST /cgi-bin/remove_member.py` |
| 目前狀態 | 尚需建立正式 API；可與現有 `update_member_role.py` 整合 |

## 目的

只撤銷成員在指定場域中的角色與權限，不影響其在其他場域的身分。

## 角色與觸發時機

**主要角色：** 該場域 Admin。

**建立上鏈事件的時機：** 指定 `user_families` 關係已刪除，或已改為 `Revoked` 且權限立即失效後。

## 相關資料表

- `user_families`
- `audit_logs`
- `ledger_events`

## 標準上鏈 JSON

```json
{
  "schema_version": "1.0",
  "uc_id": "UC3.3",
  "event_id": "UUID",
  "event_type": "MEMBER_PERMISSION_REVOKED",
  "family_id": 12,
  "gateway_id": "GW_001",
  "source": "SERVER",
  "timestamp": "2026-07-28T12:00:00+08:00",
  "actor": {
    "actor_type": "USER",
    "actor_id_hash": "sha256:ADMIN_ID_HASH",
    "actor_role": "ADMIN"
  },
  "payload": {
    "member_id_hash": "sha256:REMOVED_MEMBER_ID_HASH",
    "scope": {
      "scope_type": "FAMILY",
      "family_id": 12,
      "affects_other_families": false
    },
    "role_revocation": {
      "previous_role": "MEMBER",
      "new_role": null,
      "revoked_permissions": [
        "DEVICE_VIEW",
        "DEVICE_CONTROL",
        "DASHBOARD_VIEW"
      ]
    },
    "permission_invalid_at": "2026-07-28T12:00:00+08:00",
    "reason_code": "ADMIN_REMOVED_MEMBER",
    "operated_by_hash": "sha256:ADMIN_ID_HASH"
  }
}
```

## 必要驗證

1. Admin 不得移除場域中唯一的 Admin，除非先完成管理權移轉。
2. 不得因 UC3.3 刪除 `users` 主帳號。
3. 操作範圍必須限定在指定 `family_id`。
4. 被移除者的既有 Access Token 應於下一次授權檢查時失效。

## API 與區塊鏈組員分工

### Server API 負責

- 驗證請求、操作者、場域及資源歸屬。
- 完成業務資料更新。
- 建立 `audit_logs`。
- 呼叫 `enqueue_ledger_event()`，建立 `MEMBER_PERMISSION_REVOKED` 事件。
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
    "event_type": "MEMBER_PERMISSION_REVOKED"
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

- [ ] 成員無法再查詢或控制該場域設備。
- [ ] 成員在其他場域的角色不受影響。
- [ ] 上鏈事件中的 `affects_other_families=false`。

## 共通安全規則

1. 不得將明文密碼、Session Key、訪客明文 Token、私鑰或完整個資寫入區塊鏈。
2. 使用者識別資料原則上使用 SHA-256 雜湊後上鏈；雜湊前可由 Server 加入系統端 salt 或使用 HMAC。
3. `payload_hash` 必須由 Canonical JSON 計算，固定 UTF-8、欄位排序及緊湊分隔符。
4. `event_id` 必須唯一，並在 `ledger_events.event_id` 建立 UNIQUE constraint。
5. Gateway 或設備補發事件必須驗證簽章，不得只信任 `is_overwrite=true` 或其他 Client 自填欄位。
6. 所有時間使用 ISO 8601，建議保留 `+08:00` 或統一轉為 UTC 後以 `Z` 表示。
