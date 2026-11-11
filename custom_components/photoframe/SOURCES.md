# Photo Frame — built files provenance

Built files in `photoframe.zip` come from the submodule repository:

- **Frontend source:** https://github.com/ha-workshop/lovelace-photoframe
- **Commit (v1.9.3):** [`3fe9c861266267d4186c6f88d282dcee554a5cf1`](https://github.com/ha-workshop/lovelace-photoframe/tree/3fe9c861266267d4186c6f88d282dcee554a5cf1)
  (tag [`v1.9.3`](https://github.com/ha-workshop/lovelace-photoframe/releases/tag/v1.9.3))

The files are built by:
- `frontend/scripts/build-frontend.sh` — builds PWA (`dist/pwa/`) and card (`dist/photoframe-card.js`)
- `frontend/scripts/release.sh` — tags and publishes releases in the lovelace-photoframe repo

**APK source:** `frontend/android/` in the same submodule:
- `android/build.sh` — builds `photoframe.apk` using `aapt2`, `javac`, `d8`, `apksigner`
- Source files: `android/src/ru/smartframe/frame/` (Kotlin/Java WebView wrapper)

The CI workflow `.github/workflows/release.yml` in the parent repository orchestrates:
1. Submodule checkout at the pinned commit
2. `scripts/build-frontend.sh zip` — builds frontend files
3. `npm run apk` — builds `photoframe.apk`
4. Everything is packaged into `photoframe.zip` attached to the release

All source code is at:
- https://github.com/ha-workshop/lovelace-photoframe (card + PWA + APK)
- https://github.com/ha-workshop/ha-photoframe (integration + build pipeline)
