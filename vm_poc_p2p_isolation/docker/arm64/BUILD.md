# arm64 映像檔建置（Pi 5 原生，不需 QEMU）

說明 `iri-arm64:1.8.6` 與 `compass-arm64:spike` 怎麼建出來。compose 的用法見 `README.md`。

## 為什麼要自建

上游 `iotaledger/iri` 與 `iotacafe/compass` 映像檔只有 amd64。IRI 的 jar 本身跨平台
（內含 aarch64 的 RocksDB 函式庫），所以把 jar 放到 arm64 的 JRE 基底映像檔上就能跑。
jar 的內容與上游完全相同，沒有修改過。

## 1. 取得 jar（不進版控）

從上游 amd64 映像檔取出，只複製檔案，不需要執行它。在本資料夾（docker/arm64）執行：

    docker create --platform linux/amd64 --name tmp-iri iotaledger/iri:latest
    docker cp tmp-iri:/iri/target/iri-1.8.6-RELEASE.jar iri-build/
    docker rm tmp-iri
    docker create --platform linux/amd64 --name tmp-compass iotacafe/compass:coordinator-8306ac7
    docker cp tmp-compass:/coordinator_deploy.jar .
    docker rm tmp-compass

若上游映像檔已下架，改從備份還原現成的 arm64 映像檔（備份檔不進版控，由團隊離線保管）：

    docker load < tangle-images-arm64.tar.gz

## 2. 建置

    docker build -t iri-arm64:1.8.6 iri-build
    docker build -t compass-arm64:spike -f Dockerfile.compass .

## 3. 對照指紋（SHA-256）

    sha256sum iri-build/iri-1.8.6-RELEASE.jar coordinator_deploy.jar

應與下列一致：

    590bd8b9a0c7dd1ff8f09650f3b04ee0095c18737086673b4d72e32ae2069d87  iri-1.8.6-RELEASE.jar
    6a365a3b6c9200eb889c7cdb76807c1de1876ba49deb5b0c27e0fbddbfb9bfad  coordinator_deploy.jar

## 注意

- 基底映像檔 `eclipse-temurin:8-jre` 是浮動標籤，日後重建可能與現行映像檔略有差異。
- Dockerfile 內的 JVM 記憶體預設是 2G／4G，實際由 `one-command-tangle/docker-compose.yml` 的環境變數覆蓋。
