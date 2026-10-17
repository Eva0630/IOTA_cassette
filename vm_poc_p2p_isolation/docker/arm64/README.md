# arm64 原生覆蓋檔

Pi 5（aarch64）用：把 IRI / Compass 換成自建的 arm64 image（不需 QEMU）。

- `docker-compose.arm64.yml` → 搭配 `one-command-tangle/docker-compose.yml`
- `docker-compose.arm64.multinodes.yml` → 搭配 `multi-nodes/docker-compose.yml`

用法：`docker compose -f docker-compose.yml -f arm64/docker-compose.arm64.yml up -d`

image 由 `/mnt/usb/iota-arm64/` 的 jar + Dockerfile 建置（jar 181MB 不進版控）。
