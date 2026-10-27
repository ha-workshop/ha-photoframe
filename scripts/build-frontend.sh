#!/usr/bin/env bash
# Собрать интерфейс из подмодуля frontend/ (mZer0ne/lovelace-photoframe) в интеграцию:
#   custom_components/photoframe/frontend/photoframe-card.js  — карточка для дашбордов
#   custom_components/photoframe/frontend/pwa/                — приложение по адресу /photoframe/
#
#   scripts/build-frontend.sh                       из подмодуля (так собирает CI)
#   FRONTEND=../photoframe scripts/build-frontend.sh из рабочей копии — при разработке
#   scripts/build-frontend.sh zip                   ещё и photoframe.zip для релиза (HACS: zip_release)
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$PWD"
SRC="${FRONTEND:-$ROOT/frontend}"
OUT="$ROOT/custom_components/photoframe/frontend"

[[ -f "$SRC/package.json" ]] || { echo "Нет интерфейса в $SRC — git submodule update --init" >&2; exit 1; }
(cd "$SRC" && { [[ -d node_modules ]] || npm ci --no-audit --no-fund; } \
  && rm -rf "$OUT" && mkdir -p "$OUT" \
  && npx vite build --outDir "$OUT/pwa" --emptyOutDir >/dev/null \
  && npx vite build -c vite.card.config.ts >/dev/null \
  && cp dist/photoframe-card.js "$OUT/photoframe-card.js")
echo "✓ $OUT"

if [[ "${1:-}" == zip ]]; then
  # В архиве — содержимое custom_components/photoframe: HACS распакует его в custom_components/photoframe.
  rm -f photoframe.zip
  (cd custom_components/photoframe && zip -qr "$ROOT/photoframe.zip" . -x '__pycache__/*' '*.pyc')
  echo "✓ photoframe.zip"
fi
