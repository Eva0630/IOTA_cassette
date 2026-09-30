# UC3.5 撤銷訪客臨時令牌

## 基本資訊

| 項目 | 內容 |
|---|---|
| UC 編號 | `UC3.5` |
| Ledger Event | `GUEST_TOKEN_REVOKED` |
| 建議 API 檔名 | `revoke_guest_token.py` |
| 建議 Endpoint | `POST /cgi-bin/revoke_guest_token.py` |
| 目前狀態 | 尚需建立正式 API |

## 目的

在 Token 尚未自然過期或次數耗盡前，由 Admin 主動使其立即失效。

## 角色與觸發時機

**主要角色：** Admin 或原核發者，實際權限依 Policy 設定。

**建立上鏈事件的時機：** `guest_tokens.revoked=1`、撤銷時間與原因保存成功後。

## 相關資料表

- `guest_tokens`
- `audit_logs`
- `ledger_events`

## 標準上鏈 JSON

```json
{
  "schema_version": "1.0",
  "uc_id": "UC3.5",
  "event_id": "UUID",
  "event_type": "GUEST_TOKEN_REVOKED",
  "family_id": 12,
  "gateway_id": "GW_001",
  "source": "SERVER",
  "timestamp": "2026-07-28T14:00:00+08:00",
  "actor": {
    "actor_type": "USER",
    "actor_id_hash": "sha256:ADMIN_ID_HASH",
    "actor_role": "ADMIN"
  },
  "payload": {
    "token_id": "GT_20260728_0001",
    "token_hash": "sha256:GUEST_TOKEN_HASH",
    "previous_status": "ACTIVE",
    "new_status": "REVOKED",
    "revoked_at": "2026-07-28T14:00:00+08:00",
    "remaining_uses_at_revocation": 1,
    "revocation_reason": {
      "reason_code": "ADMIN_MANUAL_REVOCATION",
      "reason_detail_hash": "sha256:REASON_DETAIL_HASH"
    },
    "operated_by_hash": "sha256:ADMIN_ID_HASH"
  }
}
```

## 必要驗證

1. Token 必須屬於操作者可管理的場域。
2. 已撤銷 Token 重送請求時應回傳冪等成功。
3. 撤銷後所有控制入口必須先檢查 revoked 狀態。
4. 不得以 Token 明文作為上鏈識別。

## API 與區塊鏈組員分工

### Server API 負責

- 驗證請求、操作者、場域及資源歸屬。
- 完成業務資料更新。
- 建立 `audit_logs`。
- 呼叫 `enqueue_ledger_event()`，建立 `GUEST_TOKEN_REVOKED` 事件。
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
    "event_type": "GUEST_TOKEN_REVOKED"
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

- [ ] 撤銷後的 Token 即使未到期且尚有次數，也無法再使用。
- [ ] 撤銷時間、原因及操作者均有 Ledger Event。
- [ ] 重複撤銷不會產生多筆不一致事件。

## 共通安全規則

1. 不得將明文密碼、Session Key、訪客明文 Token、私鑰或完整個資寫入區塊鏈。
2. 使用者識別資料原則上使用 SHA-256 雜湊後上鏈；雜湊前可由 Server 加入系統端 salt 或使用 HMAC。
3. `payload_hash` 必須由 Canonical JSON 計算，固定 UTF-8、欄位排序及緊湊分隔符。
4. `event_id` 必須唯一，並在 `ledger_events.event_id` 建立 UNIQUE constraint。
5. Gateway 或設備補發事件必須驗證簽章，不得只信任 `is_overwrite=true` 或其他 Client 自填欄位。
6. 所有時間使用 ISO 8601，建議保留 `+08:00` 或統一轉為 UTC 後以 `Z` 表示。
