# Photo Frame — Electron Desktop App

The Electron app wraps the Photo Frame PWA in a desktop window. It opens as a normal window
with a title bar; kiosk mode (fullscreen, no window chrome) is opt-in from the app settings,
just like kiosk mode in the Home Assistant card.

## Window behavior

- **Normal window by default** — resizable, centered on the selected display.
- **Kiosk** — enable it in the frame settings on this device: *Kiosk mode on this device → On*.
  The PWA calls the shell over IPC and the window switches to kiosk/fullscreen.
- **F11** toggles kiosk for the current session without changing the saved setting.
- **Escape** is passed to the PWA (back action), not used to leave kiosk.
- In kiosk mode the app blocks display sleep; in a normal window it does not.
- The device setting is stored per dashboard path in `localStorage` (`photoframe.kiosk:<path>`).

## Connecting to Home Assistant

The app does not ship with a server address: the same build works on any network.

**First launch** opens the setup screen:

1. The app looks for Home Assistant on the local network over mDNS (`_home-assistant._tcp`).
2. Found servers are listed with their names — pick one.
3. If discovery finds nothing (multicast blocked, different subnet, Docker bridge), enter the
   address manually: `http://192.168.1.10:8123` or `homeassistant.local:8123`.

Before saving, the app checks `<address>/manifest.json`, so a wrong or unreachable address is
reported right away instead of showing an error page.

The chosen address is stored per user in `server.json` inside the app data directory:

- macOS: `~/Library/Application Support/photoframe/server.json`
- Windows: `%APPDATA%\photoframe\server.json`
- Linux: `~/.config/photoframe/server.json`

**Changing the server later** — press `Ctrl/Cmd+Alt+S` in the frame window, or start with `--setup`:

```bash
npm start -- --setup
```

If the saved server stops responding (another network, HA moved), the setup screen opens by
itself with the failed address pre-filled.

The frame and Home Assistant only need to be on the same LAN: internet access is not required.

## Install from release

Download the latest release from GitHub:

- **Linux**: `Photo.Frame-*.AppImage` (portable) or `photoframe_*_amd64.deb`
- **macOS**: `Photo.Frame-*.dmg` (universal package: Apple Silicon and Intel) or `Photo.Frame-*-mac.zip`
- **Windows**: `Photo.Frame.Setup.*.exe`
- **Android frame**: `photoframe.apk` (wall tablet, Android 5+)

> The macOS app is signed and hardened, but not notarized yet: on first launch macOS asks to confirm
> opening an app from the internet — right-click the app → **Open**, or allow it in
> *System Settings → Privacy & Security*. The Windows installer is not code-signed either, so
> SmartScreen may show *Windows protected your PC* → **More info** → **Run anyway**.

Run the AppImage:

```bash
chmod +x Photo-Frame-*.AppImage
./Photo-Frame-*.AppImage
```

## Build manually

### Prerequisites

- Node.js 22+
- Git

### macOS

```bash
cd frontend/electron
npm install
npx electron-builder --mac
# Output: dist/Photo Frame-<version>-<arch>.dmg and -mac.zip
```

### Windows

```bash
cd frontend/electron
npm install
npx electron-builder --win
# Output: dist/Photo Frame Setup <version>.exe
```

### Linux

```bash
cd frontend/electron
npm install
npx electron-builder --linux
# Output: dist/Photo Frame-<version>.AppImage
```

## Signing and notarization

Both are opt-in: without credentials the build still succeeds, it just produces an unsigned app
(or, on macOS, a signed but not notarized one). Everything lives in `package.json` → `build.mac` and
`entitlements.mac.plist`.

### macOS

`build.mac` already has `hardenedRuntime: true`, the entitlements file and `notarize: true`.
The app asks for the microphone when voice control is used, so the entitlements include
`com.apple.security.device.audio-input` (plus JIT and disabled library validation, which Electron and
the wake-word engine need). `NSMicrophoneUsageDescription` is added through `extendInfo`.

Signing picks up a **Developer ID Application** certificate from the login keychain:

```bash
security find-identity -v -p codesigning
```

Notarization needs Apple credentials. Store them once in the keychain:

```bash
xcrun notarytool store-credentials "photoframe" \
  --apple-id "you@example.com" \
  --team-id "DCZN6QFGYW" \
  --password "app-specific-password"   # appleid.apple.com → App-Specific Passwords
```

Then either export the standard variables before building:

```bash
export APPLE_ID="you@example.com"
export APPLE_APP_SPECIFIC_PASSWORD="app-specific-password"
export APPLE_TEAM_ID="DCZN6QFGYW"
npx electron-builder --mac --arm64 --publish=never
```

or point electron-builder at the stored profile / API key:

```bash
export APPLE_KEYCHAIN_PROFILE="photoframe"          # notarytool profile
# …or an App Store Connect API key:
export APPLE_API_KEY="/path/AuthKey_XXXX.p8"
export APPLE_API_KEY_ID="XXXXXXXXXX"
export APPLE_API_ISSUER="00000000-0000-0000-0000-000000000000"
```

Check the result:

```bash
codesign -dv --verbose=2 "dist/mac-arm64/Photo Frame.app"   # flags=0x10000(runtime)
codesign -d --entitlements :- "dist/mac-arm64/Photo Frame.app"
xcrun stapler validate "dist/Photo Frame-1.9.6-arm64.dmg"
```

Without the variables electron-builder prints `skipped macOS notarization` and the DMG is only signed.

### Windows

Windows needs an Authenticode certificate; there is no free option that avoids a SmartScreen warning.
electron-builder reads it from environment variables or a file:

```bash
export CSC_LINK="/path/certificate.pfx"     # or base64 of the .pfx
export CSC_KEY_PASSWORD="certificate-password"
npx electron-builder --win
```

The certificate must come from a CA (OV or EV); a self-signed one removes nothing. The modern
alternative is **Azure Trusted Signing** (works from CI, no .pfx): set `win.azureSignOptions` in
`build` and provide `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`. Until either is set,
the release installer stays unsigned and users confirm the SmartScreen prompt once.

## Custom HA URL

```bash
HA_URL=https://your-ha.local:8123/photoframe/ npm start
```

## Start options

```bash
# Start on another display (index in the system display list)
npm start -- --display=1

# Start straight into kiosk, e.g. from autostart
npm start -- --kiosk
KIOSK=1 npm start
```

Without `--kiosk`, the saved device setting is applied: `auto` and `off` open a normal window,
`on` opens kiosk.
