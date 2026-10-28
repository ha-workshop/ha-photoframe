<p align="center"><img src="https://raw.githubusercontent.com/ha-workshop/ha-photoframe/main/docs/icon.png" width="128" height="128" alt="Photo Frame"></p>

# Photo Frame — integration for Home Assistant

**English** · [Русский](README.ru.md)

**One install for the whole photo frame.** A tablet, an old phone or an Android photo frame shows your photos,
a big clock and the weather; swipe up for lights, climate, cameras, speakers and TV. This integration brings
everything with it — no separate dashboard card, no add-ons, no long-lived tokens.

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/docs/faq/custom_repositories)
[![Release](https://img.shields.io/github/v/release/ha-workshop/ha-photoframe)](https://github.com/ha-workshop/ha-photoframe/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## What you get

- **The dashboard card** `custom:photoframe-card` — available on every dashboard right after install,
  no resource to add.
- **The standalone app** at `http://<your HA>/photoframe/` — for browsers, *Add to Home Screen* and old
  Android frames (the frame app, an APK, is served by Home Assistant too — see *Android frame* below).
  It signs in through Home Assistant's own login page.
- **One shared configuration** for the card and every frame: homes, their screens and cards, slideshow
  settings — stored in Home Assistant (`.storage/photoframe`), changes show up on all frames at once.
  Photos come from the media library (`/media/photoframe`).
- **Settings in the UI** — *Settings → Devices & services → Photo Frame → Configure*: photo folder,
  kiosk mode by default, who may change homes and screens (admins or all users).

## Every frame is a device

Each frame that opens the app (APK, browser, *Add to Home Screen*) shows up in *Settings → Devices* with:

- **Online** — while the frame is connected;
- **Album** — a subfolder of the photo folder (`/media/photoframe/<album>`), or *All photos*;
- **Start screen** — where the frame starts and returns to when left alone;
- **Current photo** — with the photo as the entity picture;
- **Screen** — a light: off puts the frame to sleep (black screen, slideshow paused; a touch wakes it),
  brightness dims it (real backlight in the APK, a dark overlay in a browser). Turn it off at night
  and on from a motion sensor with an ordinary automation;
- **Frame app** (Android frames with the APK) — an update when the integration serves a newer APK; *Install*
  makes the frame download and install it (silently with root, otherwise tap *Install* on the frame);
- buttons **Next photo**, **Open panel**, **Back to photos**, **Reload**.

Services for automations (pick frames as devices; none — all online frames):
`photoframe.show_camera` (e.g. the doorbell rang — show the porch camera for 30 s), `photoframe.set_album`,
`photoframe.show_screen`, `photoframe.next_photo`. Rename a frame like any device — the frame picks the name up.

The interface itself — photo screen like the iPhone lock screen, screens per home, a separate phone
layout, charts — is described in [lovelace-photoframe](https://github.com/ha-workshop/lovelace-photoframe).

## Install

1. Open the repository in HACS:

   [![Open in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=ha-workshop&repository=ha-photoframe&category=integration)

   Or by hand: HACS → search **Photo Frame**. Not in the list yet? HACS → ⋮ → **Custom repositories** →
   `https://github.com/ha-workshop/ha-photoframe`, type **Integration**.
2. Download **Photo Frame**, restart Home Assistant.
3. Add the integration:

   [![Add integration](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=photoframe)

   (*Settings → Devices & services → Add integration → Photo Frame*.)
4. Add the **Photo Frame** card to a dashboard (a *Panel* view works best) or open `/photoframe/` on a device.

**Android frame** (wall tablet, old Android 5+): install the frame app — Home Assistant serves it at
`http://<your-ha>/photoframe/photoframe.apk` (it's also attached to every release). Open it, enter the Home Assistant
address, sign in. Photos are drawn natively (smooth even on weak tablets); the app starts on power-up, keeps
Wi-Fi awake and can switch the screen off completely for the **Screen** entity. After updating the integration
the frame gets a **Frame app** update in Home Assistant.

Already using the **Photo Frame card** from HACS (category Dashboard)? On first start the integration
copies your homes and screens from the card on the *Photo Frame* dashboard. You can keep the card
installed — the integration notices it and doesn't load a second copy — or remove it.

## Development

The interface is the [lovelace-photoframe](https://github.com/ha-workshop/lovelace-photoframe) submodule in
`frontend/`; a release builds it into the integration (`photoframe.zip`).

```bash
git clone --recursive https://github.com/ha-workshop/ha-photoframe
scripts/build-frontend.sh      # interface → custom_components/photoframe/frontend
dev/run.sh                     # test Home Assistant in Docker: http://localhost:8125
```

`FRONTEND=../lovelace-photoframe scripts/build-frontend.sh` builds from a working copy instead of the submodule.

Releasing (signing key for the APK, release steps, common CI failures): [RELEASING.md](RELEASING.md).

## License

MIT
