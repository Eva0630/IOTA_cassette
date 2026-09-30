# UC1.3 閘道器初始化與屋主綁定

## 基本資訊

| 項目 | 內容 |
|---|---|
| UC 編號 | `UC1.3` |
| Ledger Event | `SITE_GENESIS_CREATED` |
| 建議 API 檔名 | `gateway_initialize.py` |
| 建議 Endpoint | `POST /cgi-bin/gateway_initialize.py` |
| 目前狀態 | 尚需建立正式 API |

## 目的

建立第一個場域、Gateway 與屋主綁定關係，並建立該場域的創世存證事件。

## 角色與觸發時機

**主要角色：** Admin／首位屋主，且需經由本地實體連線或一次性初始化憑證。

**建立上鏈事件的時機：** `families`、Gateway 與 Admin 綁定全部成功，且 Gateway 公鑰已驗證後。

## 相關資料表

- `families`
- `user_families`
- `建議新增 gateways`
- `audit_logs`
- `ledger_events`

## 標準上鏈 JSON

```json
{
  "schema_version": "1.0",
  "uc_id": "UC1.3",
  "event_id": "UUID",
  "event_type": "SITE_GENESIS_CREATED",
  "family_id": 12,
  "gateway_id": "GW_001",
  "source": "SERVER",
  "timestamp": "2026-07-28T10:00:00+08:00",
  "actor": {
    "actor_type": "USER",
    "actor_id_hash": "sha256:OWNER_ID_HASH",
    "actor_role": "ADMIN"
  },
  "payload": {
    "owner_binding": {
      "owner_id_hash": "sha256:OWNER_ID_HASH",
      "role": "ADMIN",
      "binding_method": "PHYSICAL_LOCAL_CONNECTION",
      "bound_at": "2026-07-28T10:00:00+08:00"
    },
    "gateway": {
      "gateway_id": "GW_001",
      "hardware_model": "RASPBERRY_PI",
      "firmware_version": "1.0.0",
      "public_key_hash": "sha256:GATEWAY_PUBLIC_KEY_HASH",
      "initial_status": "ACTIVE"
    },
    "genesis": {
      "genesis_type": "FAMILY_SITE_GENESIS",
      "previous_block_hash": null,
      "configuration_hash": "sha256:INITIAL_CONFIGURATION_HASH"
    }
  }
}
```

## 必要驗證

1. 呼叫者必須是該場域第一位 Admin。
2. 同一個 `gateway_id` 不得重複綁定至不同場域。
3. Gateway 公鑰格式與所有權證明必須通過驗證。
4. 若場域已存在創世事件，應回傳冪等結果，不得再建立第二個 Genesis。

## API 與區塊鏈組員分工

### Server API 負責

- 驗證請求、操作者、場域及資源歸屬。
- 完成業務資料更新。
- 建立 `audit_logs`。
- 呼叫 `enqueue_ledger_event()`，建立 `SITE_GENESIS_CREATED` 事件。
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
    "event_type": "SITE_GENESIS_CREATED"
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

- [ ] 第一次初始化成功後，`families`、`user_families`、Gateway 資料及 `ledger_events` 同時存在。
- [ ] `ledger_events.event_type` 為 `SITE_GENESIS_CREATED`。
- [ ] 重送相同初始化請求不會產生第二筆創世事件。

## 共通安全規則

1. 不得將明文密碼、Session Key、訪客明文 Token、私鑰或完整個資寫入區塊鏈。
2. 使用者識別資料原則上使用 SHA-256 雜湊後上鏈；雜湊前可由 Server 加入系統端 salt 或使用 HMAC。
3. `payload_hash` 必須由 Canonical JSON 計算，固定 UTF-8、欄位排序及緊湊分隔符。
4. `event_id` 必須唯一，並在 `ledger_events.event_id` 建立 UNIQUE constraint。
5. Gateway 或設備補發事件必須驗證簽章，不得只信任 `is_overwrite=true` 或其他 Client 自填欄位。
6. 所有時間使用 ISO 8601，建議保留 `+08:00` 或統一轉為 UTC 後以 `Z` 表示。
