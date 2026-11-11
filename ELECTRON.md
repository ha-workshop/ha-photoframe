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

## Install from release

Download the latest release from GitHub:

- **Linux**: `Photo-Frame-*.AppImage` (portable)
- **macOS**: build manually (see below)
- **Windows**: build manually (see below)

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
# Output: dist/Photo-Frame-*.dmg
```

### Windows

```bash
cd frontend/electron
npm install
npx electron-builder --win
# Output: dist/Photo-Frame-*.exe
```

### Linux

```bash
cd frontend/electron
npm install
npx electron-builder --linux
# Output: dist/Photo-Frame-*.AppImage
```

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
