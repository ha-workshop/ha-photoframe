# AI Instructions — Photo Frame for Home Assistant

## Language
- All code comments: **English**
- All commit messages: **English**
- Release notes / changelog: **English**
- UI translations for the app: **Russian** (`ru.json`) and **English** (`en.json`) — these stay as-is, more languages welcome

## Repositories
- Integration (Python/HA backend): `github.com/ha-workshop/ha-photoframe`
- Frontend (Preact/PWA/card): submodule `frontend/` → `github.com/ha-workshop/lovelace-photoframe`

## Key architecture
- **PWA** at `/photoframe/`, served by HA integration
- **Dashboard card** (`custom:photoframe-card`) — same source, built as `dist/photoframe-card.js`
- **APK**: Android WebView shell in `frontend/android/`, built without Gradle (aapt2 → javac → d8 → zipalign → apksigner)
- **Voice assistant**: HA Assist pipeline via WebSocket + local wake word (openWakeWord WASM)
- **No external auth tokens**: signs in through HA login page or embedded session

## Code style
- TypeScript strict mode, Preact (not React), JSX
- Python: HA custom component style (`custom_components/photoframe/`)
- CSS variables for theming, two color modes (dark always)
- i18n keys: `section.key_name` in `src/i18n/locales/{ru,en}.json`

## Versioning
- Frontend version in `frontend/package.json`
- Integration version in `custom_components/photoframe/manifest.json`
- Tag both repos: `v{major}.{minor}.{patch}`
- Release both together with matching version numbers

## HACS publishing
- PR template requires: release link, HACS action run, hassfest action run
- PR author must be a public member of `ha-workshop` org or a repo collaborator
