# IOTA 專案進度

**更新**：2026-10-16 08:30　**範圍**：RPi5 部署 + 節點技術棧
**研究題目**：基於 IOTA 分散式帳本與邊緣運算之智慧家居安全防護架構研究

---

## 0. 一句話現況

**私有 Tangle 已經在 Pi 5 上跑起來了，而且是原生 arm64、不需要 QEMU。**
`debian` 這邊的整套已停機（只 stop、資料保留），專案主場移到 Pi 5。

---

## 1. 重大結論：QEMU 不需要了

原本的方案是「Pi 5 用 QEMU 模擬 amd64 跑 IRI / Compass」。實測後改為**原生 arm64 自建 image**：

| 項目 | 結果 |
|---|---|
| IRI jar | `/iri/target/iri-1.8.6-RELEASE.jar`（181MB），內含 `librocksdbjni-linux-aarch64.so` |
| Compass jar | `/coordinator_deploy.jar`（19MB） |
| 自建 image | `iri-arm64:1.8.6`、`compass-arm64:spike`（base：`eclipse-temurin:8-jre`，**arm64 原生**） |
| 驗證 | RocksDB 原生初始化成功、`IOTA Node initialised correctly`、零 `UnsatisfiedLinkError` |

**為什麼原本判斷錯**：先前只看 Maven Central 的 classifier 清單（沒有 linux-aarch64）就下結論，忽略**預設 jar 本身就打包了多平台原生庫**。

---

## 2. Pi 5 目前運作狀態（2026-10-16 實測）

| 項目 | 結果 |
|---|---|
| 容器 | `one-command-tangle-iri-1`、`one-command-tangle-compass-1`、`hornet-node-2`、`hornet-node-3` 全部 Up |
| milestone | 三節點同步遞增（30 秒內 4 → 5） |
| neighbor | 三節點各 2 條 `connected`（原生下 `setup_neighbors.sh` **一次就連上**） |
| 鏈狀態 | **全新鏈**（state/ 原本不存在，第一次 compass 帶 `-bootstrap`，之後移除） |
| 多節點一致性 | **✅ 已通過**：送出測試交易 `C9QNLJLC9MZWTXBLAWPUQBMIIRWSEQGMALT9BVKHVBMXRPYJBMZYEYUPCQSUZEDBILQOUDUREZZUYI999`，三節點（14265/14266/14267）查到**完全一致的 1 筆**，`verify_multinode.py` 輸出「多節點共同驗證通過」 |
| Heap 驗證 | `-Xms256M -Xmx768M`，`MaxHeapSize := 805306368`（= 768MB，精確命中） |

**資源（用 `/proc/<pid>/status` 的 RSS，因為主機沒開 memory cgroup）**

| 容器 | RSS |
|---|---|
| compass | ~698 MB |
| iri（主鏈） | ~189 MB |
| node2 / node3 | 各 ~165 MB |

`load average: 0.34 / 0.44 / 0.29`、`溫度 48.8°C`

> 這組數字推翻了「4 核跑 4 個 JVM 會 CPU 爆炸」的擔心——**原生 arm64 下負載極低**，Pi 5 單機全跑完全可行。

---

### 2.1 驗收證據（2026-10-16）

```
hornet-node-3                  iri-arm64:1.8.6       Up
hornet-node-2                  iri-arm64:1.8.6       Up
one-command-tangle-compass-1   compass-arm64:spike   Up
one-command-tangle-iri-1       iri-arm64:1.8.6       Up
```

- 測試交易 hash：`C9QNLJLC9MZWTXBLAWPUQBMIIRWSEQGMALT9BVKHVBMXRPYJBMZYEYUPCQSUZEDBILQOUDUREZZUYI999`
- `verify_multinode.py`：三節點一致 → **通過**
- 四容器 log 近 20 行：**無 error / exception / warn**
- 穩定後 RSS：iri ~197MB、compass ~703MB、node2/3 各 ~170MB；load 0.02–0.24；溫度 48.8°C

---
## 3. 建置產物位置（Pi 上）

```
/mnt/usb/iota-arm64/
  ├── iri-build/{Dockerfile, entrypoint.sh, iri-1.8.6-RELEASE.jar}
  ├── coordinator_deploy.jar
  ├── docker-compose.arm64.yml              → one-command-tangle 用（iri + compass）
  └── docker-compose.arm64.multinodes.yml   → node2/node3 用
```

啟動方式（取代 QEMU 覆蓋檔）：

```bash
docker compose -f docker-compose.yml -f /mnt/usb/iota-arm64/docker-compose.arm64.yml up -d
```

**`entrypoint.sh` 已原封不動搬用官方版本**，並在 Dockerfile 補回原始 ENV 預設值（`JAVA_MIN_MEMORY` / `JAVA_MAX_MEMORY` / `JAVA_OPTIONS` / `DOCKER_IRI_REMOTE*`），否則 heap 調校不會生效。

---

## 4. 尚未完成

**驗收 / 驗證**
1. ~~送測試交易驗證多節點一致性~~ **✅ 已完成**（見 §2）
2. **修正 arm64 覆蓋檔的 heap 設定**：目前實際生效是 `-Xms512M -Xmx1500M`（來自 base compose），**不是目標的 768M**——arm64 覆蓋檔只換了 image、沒帶 heap 環境變數。要在 `docker-compose.arm64*.yml` 補 `JAVA_MAX_MEMORY=768M` / `JAVA_MIN_MEMORY=256M` 後重建 iri 容器
3. **查明容器為何在檢查前 4～5 分鐘才被重建**（主機 uptime 6h23m，但四容器只 Up 4～5 分鐘）→ 可能有人在別的 session 動過，或 restart policy 觸發
2. 決定鏈要**沿用 debian 上的舊鏈**（`db/` 還在，milestone 15552）還是**留在新鏈**

**部署**
3. IOTA_API 上 Pi（image 全有 arm64，不需 QEMU）
4. 前端 build + 提供服務（API 是 **8091**）

**收尾**
5. Commit 進版控：`docker-compose.arm64*.yml`、`iri-build/`（jar 太大不建議進版控，放建置說明即可）
6. `restore.sh` 容器名、`setup_neighbors.sh` 等待時間、`start_all.sh` 邏輯
7. `OTA_HOST` 寫死 `192.168.1.3` → `192.168.1.78`
8. `http_bridge.py` 範例 `8085` → `8091`

---

## 5. 主機層限制 / 待決定

- **Pi 沒有啟用 memory cgroup controller**（`/sys/fs/cgroup/cgroup.controllers` 只有 `cpuset cpu io pids`）→ `docker stats` 的記憶體永遠顯示 `0B`。要修需在 `/boot/cmdline.txt` 加 `cgroup_enable=memory` 並**重開機**；目前先用 RSS 替代。
- `/mnt/usb` 是**一般隨身碟（29.5G）不是 SSD** → RocksDB + MySQL 寫入密集，耐久度是已知限制，建議之後換 SSD/NVMe。
- `/login` 不核發 token（來自 HANDOVER，尚未處理）。

---

## 6. 機器清單

| 機器 | 規格 | 角色 | 狀態 |
|---|---|---|---|
| Raspberry Pi 5 | aarch64 / Debian 13 / 8GB / `raspberrypi` / LAN `192.168.1.78` | **主機：鏈 + 之後的 App/後端** | ✅ 鏈運行中 |
| `debian` | x86_64（`192.168.0.134` / `192.168.100.30`） | 開發機（已停機，資料保留，milestone 15552） | ⏹ 全部 Exited |
| SMB `\\192.168.100.1\f` | — | 交付檔案 | ✅ |

**Pi 存取**：`ssh -p 2222 iota@lab1.alexc.one`（公網動態 IP，只轉發 2222；金鑰在 `debian` 的 `~/.ssh/id_ed25519`）

---

## 7. 文件

| 文件 | 位置 |
|---|---|
| 本進度文件 | repo `vm_poc_p2p_isolation/PROGRESS.md`、SMB |
| QEMU 指南（§13 已改為「原生 arm64 優先」） | repo `QEMU_ARM64.md`、SMB、PDF |
| 節點更換評估報告 v2 | workspace、SMB、PDF |

---

*依 2026-10-16 實測整理；數字均為實際指令輸出。*

---

## 9. 2026-10-17 更新：Pi 5 已完整上線（原生 arm64）

### 9.1 解決的問題：Docker whiteout 錯誤

錯誤：`failed to convert whiteout file "home/.wh.node": operation not permitted`

- **根因**：Pi 開了 **overlayroot（唯讀根目錄，upper 在 tmpfs）**，Docker 的 overlayfs 又疊在上面 → **overlay 疊 overlay**，kernel 不允許在這種 upper 建 whiteout 所需的 char device
- **修法**：`raspi-config` → Performance → Overlay File System → **Disable** → 重開機
- **驗證**：`/` 與 `/mnt/usb` 都變成 **ext4 rw**、`mknod` 可用、**`node-red` image 成功拉取**（先前就是它卡住）

### 9.2 目前運行狀態（全部在 Pi 5 上，原生 arm64）

| 元件 | 狀態 |
|---|---|
| Tangle（iri / compass / node2 / node3） | **Up**；milestone **67 / 67 / 67**（三節點一致、持續增長） |
| neighbor | 三節點各 **2 條 connected** |
| IOTA_API（mysql / mosquitto / mqtt-server / api / bridge / node-red） | **Up**；`GET /healthz` → `{"status":"ok"}` |
| mqtt-monitor（8090） | **未啟動**（dev 模式 broker 只開 1883，monitor 設定走 TLS 8883） |

啟動方式（實測有效）：

```bash
# 鏈
cd /mnt/usb/IOTA_cassette/vm_poc_p2p_isolation/docker/one-command-tangle
docker compose -f docker-compose.yml -f /mnt/usb/iota-arm64/docker-compose.arm64.yml up -d
cd ../multi-nodes
docker compose -f docker-compose.yml -f /mnt/usb/iota-arm64/docker-compose.arm64.multinodes.yml up -d
cd .. && ./setup_neighbors.sh

# 後端
cd /mnt/usb/IOTA_API
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build \
  mysql mqtt-broker mqtt-server api api-mqtt-bridge node-red
```

### 9.3 待處理

1. **mqtt-monitor**：需要一份 dev 覆蓋（走 1883）才能啟動
2. **前端**：把 `build/web` 放到 Pi 並起 8085（API 是 **8091**）
3. **`sudo` 現在要密碼**：NOPASSWD 原本寫在 overlay 暫存層，重開後消失 → 要重新設定才會持久
4. 文件 / commit 收尾（arm64 覆蓋檔、PROGRESS.md 等）
5. 用 `verify_multinode.py` 在新鏈上再跑一次三節點一致性（已於 10-16 驗過，重開後建議重跑）

---

## 10. 2026-10-17 晚間：前端上線 + 重開機韌性

### 10.1 前端（已完成）

| 項目 | 內容 |
|---|---|
| 服務 | `iota_web`（`nginx:alpine`），`--restart always`，`-p 8085:80` |
| 內容 | `/mnt/usb/webapp`（從 debian 複製的 Flutter `build/web`，41M，10/7 編，含時區修正） |
| 驗證 | `localhost:8085` → 200、`192.168.1.78:8085` → 200 |
| 掛載 | **唯讀**（`ro`），容器無法改檔 |

Pi 上**沒有安裝 Flutter SDK**（不必要）。日後更新流程：在 debian `flutter build web` → 複製 `build/web/*` 到 Pi 的 `/mnt/usb/webapp/`。

### 10.2 mqtt-monitor 改為維修模式

`docker-compose.dev.yml` 補上並加 profile：

```yaml
  mqtt-monitor:
    profiles: ["maintenance"]
    environment:
      MQTT_PORT: "1883"
      MQTT_USE_TLS: "0"
```

平常 `up -d` 不會啟動；維修時 `--profile maintenance up -d mqtt-monitor`。

### 10.3 LCD（`~/lcd_status.py`）

- 移除 `mqtt_monitor` 必要清單；8090 檢查改成「容器存在才檢查」
- I2C 開機競態：新增 `open_i2c()` 重試（40 × 1.5s），執行期 OSError 會自動重開 bus
- 新增 **uptime**（`3d 5h` 格式）與 **`/var/run/reboot-required`** 提示（`Reboot required`）

### 10.4 重開機韌性（重要教訓）

一天內三次確認同一個故障模式：

1. `restart: always` 把容器拉回來，但 **IRI 不持久化 neighbor** → 三節點 `getNeighbors` 全為 0
2. **compass 常以 `Exited (137)` 收場**：shutdown hook 要等「下一個 milestone」（最多 30s），但 `docker stop` 只給 10s → SIGKILL
3. 結果：milestone 停住（實例：卡在 83、卡在 138）

**解法**：`~/start_all.sh`（起容器 → 輪詢 `getNodeInfo` 等 IRI ready → `setup_neighbors.sh` 重試到三節點各 2 條 → 起後端），已實測 idempotent。

**仍待處理**：
- 裝 systemd unit 讓 `start_all.sh` 開機自動執行（需 sudo）
- compose 給 compass 補 `restart: always` + `stop_grace_period: 60s`（否則每次 stop 都會 137）

### 10.5 基礎設施備註

- `sudo` 現在要密碼（舊的 NOPASSWD 隨 overlay 一起消失）；`iota` 在 `docker` 群組，docker 指令不需 sudo
- `over_voltage_delta` 尚未加回 `config.txt`、`i2cdetect` 尚未安裝（兩者都要 sudo）
- HackMD 自動更新仍不可用：`HACKMD_API_TOKEN` 已在機密區，但 egress proxy 未啟用
