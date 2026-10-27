<p align="center"><img src="https://raw.githubusercontent.com/mZer0ne/ha-photoframe/main/docs/icon.png" width="128" height="128" alt="Photo Frame"></p>

# Photo Frame — integration for Home Assistant

**English** · [Русский](README.ru.md)

**One install for the whole photo frame.** A tablet, an old phone or an Android photo frame shows your photos,
a big clock and the weather; swipe up for lights, climate, cameras, speakers and TV. This integration brings
everything with it — no separate dashboard card, no add-ons, no long-lived tokens.

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/docs/faq/custom_repositories)
[![Release](https://img.shields.io/github/v/release/mZer0ne/ha-photoframe)](https://github.com/mZer0ne/ha-photoframe/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## What you get

- **The dashboard card** `custom:photoframe-card` — available on every dashboard right after install,
  no resource to add.
- **The standalone app** at `http://<your HA>/photoframe/` — for browsers, *Add to Home Screen* and old
  Android frames (an APK shell lives in [lovelace-photoframe](https://github.com/mZer0ne/lovelace-photoframe)).
  It signs in through Home Assistant's own login page.
- **One shared configuration** for the card and every frame: homes, their screens and cards, slideshow
  settings — stored in Home Assistant (`.storage/photoframe`), changes show up on all frames at once.
  Photos come from the media library (`/media/photoframe`).
- **Settings in the UI** — *Settings → Devices & services → Photo Frame → Configure*: photo folder,
  kiosk mode by default, who may change homes and screens (admins or all users).

The interface itself — photo screen like the iPhone lock screen, screens per home, a separate phone
layout, charts — is described in [lovelace-photoframe](https://github.com/mZer0ne/lovelace-photoframe).

## Install

1. HACS → ⋮ → *Custom repositories* → `https://github.com/mZer0ne/ha-photoframe`, category **Integration**.
2. Install **Photo Frame**, restart Home Assistant.
3. *Settings → Devices & services → Add integration → Photo Frame*.
4. Add the **Photo Frame** card to a dashboard (a *Panel* view works best) or open `/photoframe/` on a device.

Already using the **Photo Frame card** from HACS (category Dashboard)? On first start the integration
copies your homes and screens from the card on the *Photo Frame* dashboard. You can keep the card
installed — the integration notices it and doesn't load a second copy — or remove it.

## Development

The interface is the [lovelace-photoframe](https://github.com/mZer0ne/lovelace-photoframe) submodule in
`frontend/`; a release builds it into the integration (`photoframe.zip`).

```bash
git clone --recursive https://github.com/mZer0ne/ha-photoframe
scripts/build-frontend.sh      # interface → custom_components/photoframe/frontend
dev/run.sh                     # test Home Assistant in Docker: http://localhost:8125
```

`FRONTEND=../lovelace-photoframe scripts/build-frontend.sh` builds from a working copy instead of the submodule.

## License

MIT
