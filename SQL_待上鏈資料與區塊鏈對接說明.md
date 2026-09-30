# SQL 待上鏈資料與區塊鏈端接手說明

**目前程式會先把需要追溯的業務事件存進 MySQL 的 `ledger_events`，狀態為 `PENDING`。存入 SQL 代表「準備好等待上鏈」，真正提交 IOTA、取得交易參考值及確認結果，需要由後續 Ledger Worker 完成。**

例如 Admin 核發訪客 QR：API 先完成訪客帳號與授權，再保存「誰在何時、對哪個家庭、發出了哪一次授權」的事件。區塊鏈端接手的是這筆事件，不需要讀出或公開訪客明文密碼。

## 1. 為什麼先存 SQL，再上鏈

API 的業務操作與 IOTA 的網路提交是兩個階段。若每次 API 都等待鏈上確認，網路延遲或 IOTA 暫時無法連線會拖住 App 操作。

目前採用以下流程：

1. API 驗證請求，更新業務表。
2. 在同一個 MySQL transaction 內建立所需 audit 及 `ledger_events(PENDING)`。
3. DB commit 後回應業務結果；沒有提交的事件不應被 Worker 處理。
4. Ledger Worker 從已提交的待處理事件取資料、核對 hash、提交 IOTA。
5. Worker 將提交參考值與確認狀態回寫 SQL。

在完整 schema、正常新增事件流程下，業務更新與待上鏈事件共同提交；SQL 任一步驟失敗則不應留下半套業務資料。IOTA 暫時不可用時，已提交的 PENDING 紀錄可等待 Worker 接手。拒絕操作或重複操作的 audit 處理依各 API 分支，不代表每一筆 audit 都會有 Ledger Event。

本包目前完成第 1–3 步；第 4–5 步的 Worker 與確認回寫流程尚未包含。

## 2. 哪些 SQL 表與上鏈有關

| 資料表 | 用途 | 與上鏈的關係 |
| --- | --- | --- |
| users / user_families / families / gateways / devices | 平台帳號、家庭、角色、Gateway、設備目前狀態 | 業務資料來源；不將整張表上鏈 |
| guest_tokens | GUEST_ 令牌的 hash、期限、次數與撤銷狀態 | 核發或撤銷時擷取必要資訊建立事件 |
| device_credentials | 設備公鑰憑證目前的 Active / Revoked 狀態 | 配對及除役事件會帶相關憑證 hash / 狀態 |
| security_events | 異常類型、嚴重程度、來源、證據 hash、發生時間 | UC4.4 的本地業務紀錄；相應事件另存 ledger_events |
| physical_override_events | 預留實體覆寫來源事件、序號及簽章欄位 | 本包有表，但沒有 sync_physical_overwrite.py，未完成同步入庫 API |
| audit_logs | 本地操作稽核與 prev_hash / current_hash | 本地追溯資料；不會因寫入就自動送 IOTA |
| ledger_events | 待上鏈事件 JSON、hash、去重鍵及處理狀態 | Ledger Worker 接手的主要資料表 |

`schema.sql` 只建立或更新資料結構；真正產生事件的是 API 程式呼叫 `enqueue_ledger_event()`。只有建表不會自動產生待上鏈紀錄。

## 3. 本包哪些操作會產生 Ledger Event

| UC | 觸發程式 / 操作 | event_type | 事件內主要資訊 |
| --- | --- | --- | --- |
| UC1.3 | gateway_initialize.py → gateway_init_common.py，初始化與屋主綁定 | SITE_GENESIS_CREATED | 屋主 hash、綁定方式與時間、Gateway 公鑰 fingerprint、配置 hash |
| UC2.1 | device_pair.py，裝置配對 | DEVICE_REGISTERED_AND_PAIRED | 設備類型、初始狀態、ECDH 曲線、公鑰 / session key hash、配對時間 |
| UC2.3 | decommission_device.py，設備除役 | DEVICE_DECOMMISSIONED | 設備狀態變化、憑證撤銷、信任鏈終止、原因及操作者 hash |
| UC3.3 | update_member_role.py，撤銷非 Guest 成員 | MEMBER_PERMISSION_REVOKED | 成員 hash、家庭作用範圍、原角色、撤銷權限、失效時間、原因 |
| UC3.4 | generate_guest_qr.py，核發帳號＋QR 授權 | GUEST_TOKEN_ISSUED | QR_ authorization_id、GUEST_ACCOUNT_QR、訪客帳號 hash、期限、次數 |
| UC3.4 | update_member_role.py，設定 Guest 角色 | GUEST_TOKEN_ISSUED | ROLE_ authorization_id、GUEST_ACCOUNT_ROLE、範圍、期限、次數 |
| UC3.4 | issue_guest_token_demo.py，本包實際已加入核發驗證及事件 | GUEST_TOKEN_ISSUED | GT_ token_id、token_hash、指定設備 / allowed_actions、期限與次數 |
| UC3.5 | update_member_role.py，撤銷帳號式 Guest | GUEST_TOKEN_REVOKED | authorization_id、credential_kind、帳號 hash、撤銷時間、原因 |
| UC3.5 | revoke_guest_token.py，人工撤銷 GUEST_ 令牌 | GUEST_TOKEN_REVOKED | token_id / hash、撤銷時間、剩餘次數與原因 hash |
| UC4.4 | report_security_anomaly.py 或 alert_service.py → security_anomaly_service.py | SECURITY_ANOMALY_RECORDED | 異常類型、severity、request_id、判定、證據 hash、上游措施及通知資訊 |

目前共用事件流程涵蓋 7 種 event_type；UC3.4、UC3.5 各有不同憑證來源，不能只看事件名稱就認定都是同一種 Token。

UC4.4 僅允許 `ILLEGAL_CONTROL_ATTEMPT`、`DEVICE_OFFLINE`、`BRUTE_FORCE_ATTEMPT`、`TOKEN_ABUSE`、`REPLAY_ATTACK`、`SIGNATURE_VERIFICATION_FAILED`、`UNAUTHORIZED_DEVICE`、`DEVICE_TAMPERING`。一般控制成功、普通狀態回報及一般角色更新，不會因這次新增的共用服務就自動建立上述 Ledger Event。



## 4. ledger_events 各欄位在做什麼

| 欄位 | 用途 | 屬於事件內容或處理資訊 |
| --- | --- | --- |
| event_id | 事件唯一識別，本包新建事件使用 UUID；Worker 重試沿用 | 事件 envelope 也有相同 event_id |
| dedup_key | 業務去重鍵，schema 設 UNIQUE；同一次操作避免重複事件 | SQL 索引欄位；共用 envelope 不自動包含 |
| uc_id / event_type | 使用案例與事件種類 | SQL 欄位與 envelope 都有 |
| family_id / gateway_id / device_id | 家庭、Gateway、設備範圍與查詢索引 | envelope 也帶範圍；device_id 無值時可不出現 |
| created_by | Server 端操作者 ID，便於本地追溯 | SQL 本地欄位，不自動放進 envelope；actor 通常使用 hash |
| payload | JSON 欄位，保存完整待上鏈事件 | 主要事件內容，含 envelope 和內層業務 payload |
| payload_hash | 對完整 payload JSON 做 canonical JSON 後的 SHA-256；64 位 hex | SQL 核對值，不在共用 envelope 中自動加頂層 hash |
| status | 待處理 / 提交 / 確認等狀態；新增 PENDING | Worker 處理資訊，不在原事件 hash 內容中 |
| ledger_reference | IOTA 提交成功後的可追溯參考值，具體格式由 Worker 所用介面決定 | 處理資訊；新建時 NULL |
| retry_count / last_error | 重試次數與最後錯誤，供故障處理 | 處理資訊；新建 retry_count=0 |
| created_at | Server 入庫時間，DB 預設產生 | 不同於 envelope.timestamp 的事件時間 |
| submitted_at / confirmed_at | 實際提交及取得確認的時間 | Worker 應在相應階段回寫 |
| updated_at | 資料列最近更新時間，DB 自動維護 | 處理資訊 |

SQL 的 `payload` 欄位是**整份事件**；其中還有一個 JSON `payload` 屬性，只放該 UC 的業務細節。這兩層名稱相同，但內容範圍不同。Worker 的核對對象是 SQL 整個 payload 欄位。

各 API 回給 App 的 `ledger_event` 通常只是一小份 metadata（event_id、status、hash 等）；Worker 仍需讀 SQL 的完整 payload，不能拿 App 回應 metadata 直接當上鏈事件。重複操作的 API 有時回傳完整 DB row，實際形狀依入口而異。

## 5. 一筆帳號＋QR 授權事件範例

假設家庭 12 的 Admin 發出一次可使用 3 次、一小時後到期的訪客 QR 授權。以下是依共用服務格式建立的**示意完整事件**，不是實際 DB 測試資料；示例 hash 使用本包的同一套 serializer 計算。

```json
{
  "schema_version": "1.0",
  "uc_id": "UC3.4",
  "event_id": "8aa5b9c2-5c4b-4f08-9cb5-4d163c0119a1",
  "event_type": "GUEST_TOKEN_ISSUED",
  "family_id": 12,
  "gateway_id": "GW_001",
  "source": "SERVER",
  "timestamp": "2026-09-30T13:30:00Z",
  "actor": {
    "actor_type": "USER",
    "actor_id_hash": "sha256:f51739fd6372274f543ab95b3aebfa03c824f976392bf40bb8cdca23b164fc22",
    "actor_role": "ADMIN"
  },
  "payload": {
    "authorization_id": "QR_8cd4061785d54891b7b77b0c2bc39401",
    "credential_kind": "GUEST_ACCOUNT_QR",
    "guest_user_id_hash": "sha256:22149b2f0c4cbfffff279d85f87502035d2ab8a3d06d676d17d7cbdcb6a6dde0",
    "authorization_scope": {
      "scope_type": "FAMILY",
      "family_id": 12,
      "role": "GUEST",
      "policy_enforced_by": "GATEWAY"
    },
    "validity": {
      "valid_from": "2026-09-30T13:30:00Z",
      "expires_at": "2026-09-30T14:30:00Z"
    },
    "usage_limit": {
      "max_uses": 3
    },
    "authorization_status": "ACTIVE"
  }
}
```

這筆事件對應的 SQL 索引 / 處理欄位：

| 欄位 | 範例值 |
| --- | --- |
| event_id | 8aa5b9c2-5c4b-4f08-9cb5-4d163c0119a1 |
| dedup_key | UC3.4:GUEST_TOKEN_ISSUED:GRANT:QR_8cd4061785d54891b7b77b0c2bc39401 |
| created_by | admin001（只在 SQL 本地欄位） |
| status | PENDING |
| payload_hash | eb549aac05a8b15e969d5e9a221c9dc3329cff987ca0f26c926b8637649b02d2 |
| ledger_reference | NULL |
| retry_count | 0 |

本例沒有 device_id，因為這支 QR API 的授權作用範圍是家庭。SQL device_id 為 NULL；完整事件也省略該欄位。沒有明文 password、control_url 或 guest_token。

## 6. 訪客授權的三種識別不要混用

| 識別 / 類型 | 來源 | 用途 |
| --- | --- | --- |
| QR_ authorization_id / GUEST_ACCOUNT_QR | generate_guest_qr.py | 一次帳號＋QR 授權；存 user_families.guest_grant_id |
| ROLE_ authorization_id / GUEST_ACCOUNT_ROLE | update_member_role.py 設定 Guest | 一次帳號角色授權；存 guest_grant_id，不生成 QR 或密碼 |
| LEGACY_ authorization_id / LEGACY_GUEST_ACCOUNT | 撤銷沒有授權 ID 的舊 Guest | 補上本次生命週期識別，後續重送沿用 |
| GT_ token_id | issue_guest_token_demo.py | guest_tokens 表的令牌內部 ID；供核發與撤銷追溯 |
| GUEST_ guest_token | 同上核發回應 | 明文控制憑證；DB 保存其 token_hash，不能公開上鏈 |

帳號式事件由 credential_kind 區分 QR、角色或舊帳號；本包 GUEST_ 令牌事件沒有填 credential_kind，使用 token_id、token_hash 及 authorization_scope 的結構辨識。不要假設所有 UC3.4 payload 都有 authorization_id，也不要假設所有 authorization_scope 都是相同型別：帳號式是 object，令牌式是 array。

帳號式 Guest 撤銷的 remaining_uses_at_revocation 目前為 null，不能自行解讀為 0。Token API 的剩餘次數則由 max_uses-used_count 計算。

## 7. 三種 hash 的差別與驗證方式

| Hash | 計算內容 | 用途 |
| --- | --- | --- |
| ledger_events.payload_hash | 完整待上鏈事件 envelope + 業務 payload 的 canonical JSON | 核對準備提交的事件是否與入庫內容一致 |
| audit_logs.current_hash / prev_hash | 該 audit writer 定義的稽核欄位與前一筆 hash | 本地鏈式稽核；各 writer 的欄位 / JSON 格式可能不同 |
| 事件內的 *_hash | 單項資料，例如帳號、Token、公鑰、原因或證據 | 減少原始資料暴露，供追溯比對 |

這些 hash 不是彼此可互換的數值；hash 本身也不是來源簽章、身份驗證或鏈上確認。SQL 中的 payload 與 payload_hash 若一起被修改，兩者仍可能吻合；本地 hash 核對不等於 SQL 資料不可竄改。上鏈存證後，才能另用鏈上已保存的 hash 比對目前 SQL 內容。

共用 canonical JSON 規則：UTF-8、ensure_ascii=False、sort_keys=True、separators=(",", ":")；日期使用服務的 ISO 序列化。MySQL 讀回 JSON 的空白或 key 順序可能改變，應先解析成物件，再用相同 helper 重建 canonical JSON。不要直接 hash 資料庫顯示的格式化字串，也不要只 hash 內層 event["payload"]。

Worker 核對範例（row 是從 ledger_events 讀出的 dict，以下沒有連線或提交 IOTA）：

```python
import json
from common.ledger_event_service import canonical_json, sha256_hex

raw = row["payload"]
event = json.loads(raw) if isinstance(raw, (str, bytes, bytearray)) else raw
if not isinstance(event, dict):
    raise ValueError("ledger payload must be an object")

actual_hash = sha256_hex(canonical_json(event))
if actual_hash != row["payload_hash"]:
    raise ValueError("ledger payload hash mismatch")
if event["event_id"] != row["event_id"]:
    raise ValueError("ledger event_id mismatch")

# 核對成功後，才進入 Worker 所實作的提交程序。
```

資料庫 payload_hash 存不帶 `sha256:` 的 64 位 hex；事件內 actor_id_hash / token_hash 等常帶 `sha256:`，比較時要辨識其格式。

## 8. 區塊鏈組員要接手哪些工作

目前 `ledger_event_service.py` 只建立 PENDING 事件，沒有 Worker、claim / confirm / fail API 或 IOTA SDK / RPC 提交流程。下列是後續對接工作，不是本包已有的可呼叫介面：

1. 安全領取已提交的待處理事件，避免多個 Worker 同時送同一筆。
2. 讀完整 payload，核對 canonical hash 與 event_id / UC / 範圍欄位的一致性。
3. 決定鏈上承載內容，並實作所選 IOTA 介面的提交。
4. 送出後保存可追溯的 ledger_reference、submitted_at，確認後寫 confirmed_at / CONFIRMED。
5. 處理暫時失敗、重試、永久失敗，以及送出成功但回寫 SQL 失敗的恢復。

鏈上資料有兩種可採用的對接方式：

| 方式 | 鏈上承載 | 查證方式 |
| --- | --- | --- |
| 完整事件 | 經確認可公開的完整 event JSON | 鏈上可讀事件，並核對 canonical payload_hash |
| 事件雜湊存證 | event_id + payload_hash，必要時加 uc_id / event_type 等定位資訊 | 完整 payload 保留 SQL；日後重算 hash 與鏈上存證比對 |

本包還沒有選定或實作其中一種鏈上提交方式。若採 hash 存證，event_id + payload_hash 足以作事件定位與內容比對的基礎；實際鏈上格式、索引、保存及查詢方式仍需由區塊鏈端設計。

讀取待處理事件的 SQL **僅供人工檢查**，不是安全領取 Worker 的完整實作：

```sql
SELECT event_id, uc_id, event_type, family_id, gateway_id, device_id,
       payload, payload_hash, status, retry_count, created_at
FROM ledger_events
WHERE status = 'PENDING'
ORDER BY created_at, event_id
LIMIT 20;
```

正式 Worker 需搭配交易鎖定、claim 狀態或租約，並實作當 Worker 中斷時的恢復；不要讓多個程序只 SELECT 後直接送鏈。event_id 不變可以協助追蹤，但不會自動讓 IOTA 的多次提交變成同一筆交易。

## 9. 狀態怎麼解讀

| status | 意義 | 目前實作狀態 |
| --- | --- | --- |
| PENDING | 完整事件已寫 SQL，等待上鏈 | 本包 API 會新增此狀態 |
| PROCESSING | Worker 已領取並正在處理 | 後續 Worker 設計，尚未實作 |
| SUBMITTED | 已送出並保存鏈上提交參考值 | 後續 Worker 回寫 |
| CONFIRMED | 依所用 IOTA 介面確認提交結果 | 後續 Worker 回寫 |
| RETRY | 可安全重試的暫時失敗 | 後續需定義次數、等待及領取策略 |
| DEAD_LETTER | 不可重試或已超出重試政策，等待人工處理 | 後續 Worker 設計 |

schema 的 status 是 VARCHAR，並沒有用 ENUM 限制上述值，也沒有觸發器自動切換。除了新增 PENDING，其他狀態與轉移都需實作。

提交結果不明時應先查鏈或根據提交參考值恢復，不能只因逾時就當作未送出並盲目重送。只有填入 ledger_reference 並取得所定義的確認結果後，才可以宣稱已上鏈 / 已確認；API HTTP 200 / 201 不代表此結果。

## 10. 去重範圍與重送行為

| 流程 | dedup_key 的主要組成 | 重送行為 |
| --- | --- | --- |
| Gateway Genesis | UC1.3 + FAMILY:{family_id} | 同家庭不重複建立 Genesis |
| 設備配對 | UC2.1 + 家庭 + device_id + session_key_hash | 重新產生 session key 可能是新事件，不是只靠 device_id 去重 |
| 設備除役 | UC2.3 + 家庭 + device_id | 不重複除役 Ledger；重送仍可能新增 NOOP audit |
| QR / Guest 角色核發 | UC3.4 + GRANT:{authorization_id} | 每次核發新授權 ID；重送核發請求可產生新事件 |
| GUEST_ 令牌核發 | UC3.4 + TOKEN:{token_id} | 每次核發新 Token；不提供 request_id 級核發去重 |
| 帳號式 Guest 撤銷 | UC3.5 + GRANT:{authorization_id} | 同授權不重複撤銷事件，MQTT 同步仍可重送 |
| Token 撤銷 | UC3.5 + TOKEN:{token_id} | 同 Token 不重複人工撤銷事件 |
| 非 Guest 成員撤銷 | UC3.3 + 家庭 + 成員 hash 前綴 + 撤銷時間 | 已 Revoked 分支查既有鍵，不重複新增 |
| 安全異常 | UC4.4 + 家庭 + request_id + anomaly_type | 資料庫去重；MQTT 通知仍重送，HTTP 缺 request_id 時無重送去重保證 |

API 的業務去重、MQTT 通知重送、Worker 提交重試是三個不同層次。SQL 的 UNIQUE dedup_key 只能避免使用相同鍵重複入庫；不保證 HTTP 每次請求、MQTT App 通知或鏈上提交都只發生一次。

## 11. 哪些資料不能直接公開上鏈

不要把 users、user_families、guest_tokens 或 audit_logs 整列直接序列化到鏈上。應使用已整理的事件內容，並確認鏈上可公開範圍。

| 資料 | 目前處理 / 對接限制 |
| --- | --- |
| 密碼、訪客 QR URL、GUEST_ 明文 Token | 不放入共用事件；這些是可用憑證，不能公開 |
| Gateway / 設備 private key、明文 session key | 不放上鏈；配對事件帶的是公鑰與 session key hash |
| 帳號及操作者 | 事件通常使用 hash；SQL created_by / audit 本地欄位仍可能是明文 ID |
| family_id / gateway_id / device_id / token_id / authorization_id | 本包部分事件會保留明文識別；不能宣稱事件完全匿名 |
| 異常 IP / 原始 request payload | 共用服務在缺上游 hash 時雜湊後放事件；上游提供的 hash 不會再獨立驗證 |
| 通知與封鎖回報 | request_blocked / notification_dispatched 表示輸入或當時狀態，不是實際執行或送達證明 |

MQTT alert 的紀錄分支會在發通知前把 notification_dispatched 設為 false，之後不回寫已計算 hash 的事件。這不能解讀為後續絕對沒有通知，也不能由 publish rc 成功宣稱 App 已收到。

若要改變事件公開欄位或 hash 計算規則，需要先同步 API / Worker 格式與 schema_version；不要讓 Worker 在提交前任意刪欄位，再拿刪改後 JSON 與原 payload_hash 比較。若採最小 hash 存證，保留原 payload_hash 作原始完整事件的存證值。

## 12. 程式分工與目前邊界

| 程式 / 元件 | 責任 |
| --- | --- |
| 業務 API | 驗證角色與資源、修改業務資料、建立對應 audit / 事件；驗證範圍依各入口 |
| common/audit_log_service.py | 寫本地 audit 與 hash chain，不提交 IOTA；部分舊 API 仍使用各自 writer |
| common/ledger_event_service.py | 建立完整事件、計算 hash、依鍵去重及 INSERT；不 commit / rollback |
| common/security_anomaly_service.py | UC4.4 驗證、寫業務 / audit / Ledger，自己 commit / rollback；呼叫端關閉 conn |
| alert_service.py | 嘗試異常紀錄後分權推播；與上鏈確認分開 |
| 後續 Ledger Worker | 領取、核對、提交、查確認、回寫狀態及處理重試；本包尚未提供 |

本文件描述的是目前 SQL 待上鏈資料與後續交接需求，不代表 UC4.5、Ledger Worker、鏈上確認或實機端到端驗收已完成。HTTP 與 MQTT 警報入口原 DB_NAME 預設不同，部署時需指向同一個正確資料庫，Worker 也需讀該資料庫。
