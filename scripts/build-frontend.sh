#!/usr/bin/env bash
# Собрать интерфейс из подмодуля frontend/ (ha-workshop/lovelace-photoframe) в интеграцию:
#   custom_components/photoframe/frontend/photoframe-card.js  — карточка для дашбордов
#   custom_components/photoframe/frontend/pwa/                — приложение по адресу /photoframe/
#   custom_components/photoframe/frontend/pwa/photoframe.apk  — APK рамки: HA раздаёт его по /photoframe/photoframe.apk
#
#   scripts/build-frontend.sh                       из подмодуля (так собирает CI)
#   FRONTEND=../photoframe scripts/build-frontend.sh из рабочей копии — при разработке
#   scripts/build-frontend.sh zip                   ещё и photoframe.zip для релиза (HACS: zip_release)
#
# APK собирается, если есть Android SDK (в CI он есть); в архиве релиза он обязателен. Версия APK — версия
# интеграции из manifest.json, подпись — ключом KEYSTORE (см. frontend/android/build.sh).
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

SDK="${ANDROID_HOME:-$HOME/Library/Android/sdk}"
if [[ -d "$SDK/build-tools" ]]; then
  # VERSION — своя версия (./deploy.sh integration из lovelace-photoframe ставит -dev), иначе из manifest.json.
  VERSION="${VERSION:-$(node -p "require('./custom_components/photoframe/manifest.json').version")}"
  APK_VERSION="$VERSION" "$SRC/android/build.sh" >/dev/null 2> >(grep -v "^Note:" >&2)
  cp "$SRC/android/build/photoframe.apk" "$OUT/pwa/photoframe.apk"
  echo "✓ $OUT/pwa/photoframe.apk ($VERSION)"
elif [[ "${1:-}" == zip ]]; then
  echo "Нет Android SDK — релиз без APK собирать нельзя" >&2
  exit 1
else
  echo "· APK пропущен: нет Android SDK"
fi

if [[ "${1:-}" == zip ]]; then
  # В архиве — содержимое custom_components/photoframe: HACS распакует его в custom_components/photoframe.
  rm -f photoframe.zip
  (cd custom_components/photoframe && zip -qr "$ROOT/photoframe.zip" . -x '__pycache__/*' '*.pyc')
  echo "✓ photoframe.zip"
fi
