# Pi5 操作手冊（IOTA 鏈與 Ledger）

## 0. 基本資訊

- Pi：192.168.1.78（路由器以 MAC 綁定位址），帳號 iota
- 資料庫、API、鏈的資料都在 /mnt/usb（隨身碟，非 SSD）
- 資料庫與稽核紀錄的時間是 UTC，台灣時間要加 8 小時
- 長指令請在 tmux 內執行：先輸入 tmux new -s demo，等 2 秒再貼指令；斷線後用 tmux attach -t demo 接回

## 1. 開機

插電即可，約 3 到 5 分鐘全部自動接回（iota-start、ledger-worker 都已啟用）。
不要手動執行 docker compose。

## 2. 健康檢查（開機後、demo 前都跑一次）

    for p in 14265 14266 14267; do echo -n "port $p: "; curl -s -m 5 localhost:$p -X POST -H 'Content-Type: application/json' -H 'X-IOTA-API-Version: 1' -d '{"command":"getNodeInfo"}' | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['latestMilestoneIndex'], d['latestSolidSubtangleMilestoneIndex'], 'neighbors', d['neighbors'])"; done
    systemctl is-active docker iota-start ledger-worker
    curl -s localhost:8091/healthz; echo
    ~/tamper_run.sh check

正常：三個節點數字相近、neighbors 各 2、一分鐘後 milestone 增加約 2；
三個服務 active；healthz 回 ok；tamper_run.sh check 全部 ✅。

## 3. 關機

    sudo shutdown now

關機時會依序停鏈（compass、node2/3、iri），約 1 分鐘，紀錄在 ~/stop_chain.log。
不要直接拔電：鏈曾因跳電停在半個 milestone，之後永遠無法出新的 milestone。

## 4. 出事時

### 鏈卡住

症狀：milestone 兩分鐘以上沒增加，或 docker logs --tail 5 one-command-tangle-compass-1 一直出現 Node not solid。
做法：不要重啟容器，直接重置（鏈與資料庫必須一起重置，見第 5 節）。

### 事件一直停在 PENDING、RETRY 或 DEAD_LETTER

    docker exec iot_mysql sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" devicemanagement -e "SELECT LEFT(event_id,8) id, event_type, status, retry_count, LEFT(last_error,60) err FROM ledger_events;"' 2>&1 | grep -v Warning
    journalctl -u ledger-worker.service -n 30 --no-pager

不要手動改事件狀態。Worker 查不到鏈上存證時不會自動重送，需要人工判斷。
來不及處理就直接重置。

## 5. 重置到乾淨的 demo 狀態

重置前先通知 API 與硬體同學，會清空整個資料庫與鏈。

    tmux new -s demo
    ~/demo_reset.sh --check     # 只檢查，不改任何東西
    ~/demo_reset.sh             # 輸入 RESET，再設定 Admin0123456789 的密碼（輸入時不顯示）

約 10 到 12 分鐘。結尾出現「重置完成」且竄改偵測為 3/3 才算成功。
密碼請存在密碼管理工具。資料庫與鏈必須一起重置，不要單獨還原資料庫或單獨重建鏈。

## 6. 竄改偵測展示

只有 ledger 事件（場域建立、裝置配對、裝置除役）會上 IOTA 鏈。

    ~/tamper_run.sh check      # 1. 一切正常
    ~/tamper_run.sh tamper     # 2. 改資料庫的場域屋主，並連資料庫自己的雜湊一起重算
    ~/tamper_run.sh check      # 3. 資料庫自己看不出異常，鏈上存證對不上，被抓出
    ~/tamper_run.sh restore    # 4. 還原（務必執行）
    ~/tamper_run.sh check      # 5. 回到正常

~/tamper_run.sh tamper --payload-only 只改內容、不改雜湊，連資料庫自己的雜湊都對不上。
每次展示結束一定要 restore；有未還原的竄改時 demo_reset.sh 會拒絕執行。

現場新增裝置：用 App 配對一個尚未登記過的裝置（device_id 不可重複，已除役的也不行），
約一分鐘內 Worker 自動上鏈，再執行 check
