#!/usr/bin/env bash
# Тестовый Home Assistant в Docker с интеграцией из этого репозитория: http://localhost:8125
#   dev/run.sh          поднять (или перезапустить, чтобы подхватить правки Python)
#   dev/run.sh logs     логи интеграции
#   dev/run.sh down     остановить и удалить контейнер (конфиг в dev/config остаётся)
set -euo pipefail
cd "$(dirname "$0")/.."

NAME=photoframe-test
IMAGE="ghcr.io/home-assistant/home-assistant:${HA_VERSION:-2026.10.2}"

case "${1:-up}" in
  logs) docker logs "$NAME" 2>&1 | grep -i -E "photoframe|error" | tail -50 ;;
  down) docker rm -f "$NAME" >/dev/null && echo "остановлен" ;;
  up)
    mkdir -p dev/config/media/photoframe
    if docker ps -a --format '{{.Names}}' | grep -qx "$NAME"; then
      docker restart "$NAME" >/dev/null
    else
      docker run -d --name "$NAME" -p 8125:8123 \
        -v "$PWD/dev/config:/config" \
        -v "$PWD/custom_components/photoframe:/config/custom_components/photoframe" \
        -v "$PWD/dev/config/media:/media" \
        -e TZ=Europe/Moscow "$IMAGE" >/dev/null
    fi
    for _ in $(seq 1 60); do curl -sf -o /dev/null http://localhost:8125/manifest.json && break; sleep 2; done
    echo "✓ http://localhost:8125"
    ;;
esac
