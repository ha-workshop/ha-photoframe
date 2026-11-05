# Photo Frame — Electron Desktop App

The Electron app wraps the Photo Frame PWA in a fullscreen window with no browser chrome.
It behaves like a native app: kiosk mode, power save blocker, back button support.

## Install from release

Download the latest release from GitHub:

- **Linux**: `Photo-Frame-*.AppImage` (portable) or `photo-frame_*.deb` (Debian/Ubuntu)
- **macOS**: build manually (see below)
- **Windows**: build manually (see below)

Run the AppImage:

```bash
chmod +x Photo-Frame-*.AppImage
./Photo-Frame-*.AppImage
```

Or install the .deb:

```bash
sudo dpkg -i photo-frame_*.deb
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
# Output: dist/Photo-Frame-*.AppImage, dist/photo-frame_*.deb
```

### Custom HA URL

```bash
HA_URL=https://your-ha.local:8123 DEBUG=1 npm start
```

`DEBUG=1` disables kiosk mode and shows the window frame.
