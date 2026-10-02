# UC4.4 接收分權通知與異常推播

## 基本資訊

| 項目 | 內容 |
|---|---|
| UC 編號 | `UC4.4` |
| Ledger Event | `SECURITY_ANOMALY_RECORDED` |
| 建議 API 檔名 | `report_security_anomaly.py` |
| 建議 Endpoint | `POST /cgi-bin/report_security_anomaly.py` |
| 目前狀態 | 尚需建立異常事件接收、分類與上鏈 API |

## 目的

只將具安全或責任追溯價值的異常事件上鏈；普通操作通知與一般狀態推播不需上鏈。

## 角色與觸發時機

**主要角色：** Policy Engine、Gateway、Heartbeat Monitor 或 Server 安全模組。

**建立上鏈事件的時機：** 事件通過異常分類規則，`is_abnormal=true` 且類型位於上鏈白名單後。

## 相關資料表

- `建議新增 security_events`
- `notifications`
- `audit_logs`
- `ledger_events`

## 標準上鏈 JSON

```json
{
  "schema_version": "1.0",
  "uc_id": "UC4.4",
  "event_id": "UUID",
  "event_type": "SECURITY_ANOMALY_RECORDED",
  "family_id": 12,
  "gateway_id": "GW_001",
  "device_id": "ESP32_LOCK_001",
  "source": "POLICY_ENGINE",
  "timestamp": "2026-07-28T15:30:00+08:00",
  "actor": {
    "actor_type": "UNKNOWN_OR_USER",
    "actor_id_hash": "sha256:SUSPECT_ACTOR_HASH",
    "actor_role": "UNKNOWN"
  },
  "payload": {
    "is_abnormal": true,
    "anomaly_type": "ILLEGAL_CONTROL_ATTEMPT",
    "severity": "HIGH",
    "request_id": "REQ_20260728_00123",
    "detection": {
      "detected_by": "POLICY_ENGINE",
      "policy_decision": "DENY",
      "reason_code": "PERMISSION_DENIED",
      "attempt_count": 5,
      "observation_window_seconds": 60
    },
    "source_evidence": {
      "source_ip_hash": "sha256:SOURCE_IP_HASH",
      "request_payload_hash": "sha256:REQUEST_PAYLOAD_HASH",
      "evidence_hash": "sha256:EVIDENCE_HASH"
    },
    "system_action": {
      "request_blocked": true,
      "temporary_lockout": true,
      "lockout_seconds": 300
    },
    "notification": {
      "notification_dispatched": true,
      "notified_roles": [
        "ADMIN"
      ]
    }
  }
}
```

## 必要驗證

1. 只有 `ILLEGAL_CONTROL_ATTEMPT`、`DEVICE_OFFLINE`、`BRUTE_FORCE_ATTEMPT`、`TOKEN_ABUSE`、`REPLAY_ATTACK`、`SIGNATURE_VERIFICATION_FAILED`、`UNAUTHORIZED_DEVICE`、`DEVICE_TAMPERING` 等白名單類型可上鏈。
2. 一般控制成功、正常上線、電量變化等普通推播不得建立 Ledger Event。
3. 通知對象依場域角色過濾，不得向其他場域成員洩漏異常資訊。
4. IP、裝置原始封包及個資需雜湊或留在本機。

## API 與區塊鏈組員分工

### Server API 負責

- 驗證請求、操作者、場域及資源歸屬。
- 完成業務資料更新。
- 建立 `audit_logs`。
- 呼叫 `enqueue_ledger_event()`，建立 `SECURITY_ANOMALY_RECORDED` 事件。
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
    "event_type": "SECURITY_ANOMALY_RECORDED"
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

- [ ] 異常事件會產生通知及 Ledger Event。
- [ ] 普通通知只寫一般通知資料，不會建立 Ledger Event。
- [ ] 同一 request_id 與 anomaly_type 在去重時間窗內不會重複上鏈。

## 共通安全規則

1. 不得將明文密碼、Session Key、訪客明文 Token、私鑰或完整個資寫入區塊鏈。
2. 使用者識別資料原則上使用 SHA-256 雜湊後上鏈；雜湊前可由 Server 加入系統端 salt 或使用 HMAC。
3. `payload_hash` 必須由 Canonical JSON 計算，固定 UTF-8、欄位排序及緊湊分隔符。
4. `event_id` 必須唯一，並在 `ledger_events.event_id` 建立 UNIQUE constraint。
5. Gateway 或設備補發事件必須驗證簽章，不得只信任 `is_overwrite=true` 或其他 Client 自填欄位。
6. 所有時間使用 ISO 8601，建議保留 `+08:00` 或統一轉為 UTC 後以 `Z` 表示。
