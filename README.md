# 📱 NanoPiViewer

[![GitHub Release](https://img.shields.io/github/v/release/Naloger/NanoPiViewer?include_prereleases&style=flat-square)](https://github.com/Naloger/NanoPiViewer/releases)
[![Platform](https://img.shields.io/badge/platform-Windows%20x64-blue.svg?style=flat-square)](https://github.com/Naloger/NanoPiViewer)
[![Android](https://img.shields.io/badge/target-Android%205.1%20%7C%20API%2022-brightgreen.svg?style=flat-square)](https://github.com/Naloger/NanoPiViewer)
[![License](https://img.shields.io/badge/license-MIT-green.svg?style=flat-square)](LICENSE)

A high-performance, low-latency, standalone screen streaming and remote-control application specifically designed for the **FriendlyARM NanoPi 2** (Samsung S5P4418 SoC running Android 5.1 Lollipop / API 22) and similar embedded Android single-board computers (SBCs).

---

## 📖 Background & Motivation

### Why Traditional Tools (like `scrcpy`) Fail on S5P4418
1. **Driver Bug in Hardware AVC Encoder:** The Samsung S5P4418 Board Support Package (BSP) hardware video encoder (`OMX.NX.VIDEO_ENCODER.avc`) has an unpatched vendor driver bug that outputs solid green frames (`0x00` chroma) when capturing from a virtual display surface.
2. **Missing Surface-Input in Software Encoder:** Google's software AVC encoder (`OMX.google.h264.encoder`) on Android 5.1 (API 22) does not support encoding directly from a `Surface` (a feature introduced in Android 7.0 Nougat), resulting in fatal `IllegalStateException` crashes.
3. **High Latency of Standard CPU Screencap:** Standard `screencap` utilities execute on the CPU and take **2.5 to 3.5 seconds per frame**, making real-time interaction impossible.

### How NanoPiViewer Solves This
`NanoPiViewer` integrates OpenSTF's native C++ **`minicap`** binary and SDK-specific shared library (`minicap.so`). By hooking directly into Android's `SurfaceFlinger` composition pipeline in memory and encoding frames using **ARM NEON SIMD hardware-accelerated JPEG compression**, it achieves **30–60 FPS at <50ms latency** with ultra-low CPU overhead.

---

## 🌐 Network & Port Architecture

| Port | Protocol | Purpose & Why It Is Needed |
| :--- | :--- | :--- |
| **`5555`** | TCP (ADB) | **Android Debug Bridge Daemon (`adbd`):** Used by the host PC to inject touch events (`input tap/swipe`), dispatch hardware keycodes (`input keyevent`), manage power states, and establish port forwards. |
| **`1717`** | TCP (Localhost) | **Minicap Stream Port:** Host port mapped to the Android Unix domain abstract socket `localabstract:minicap`. Receives the binary header and real-time JPEG frame stream. |

### Supported Connection Topologies
- **Local Wi-Fi Network:** PC and NanoPi 2 connect to the same wireless router (e.g. `192.168.1.xxx`).
- **Direct Ethernet Cable (Peer-to-Peer):** PC Ethernet port connected directly to NanoPi 2 `eth0` with static IP or link-local APIPA (`169.254.x.x` / `192.168.137.x`) for near-zero network jitter and maximum throughput.
- **USB OTG / USB Tethering:** Direct USB ADB connection.

---

## ⚙️ Board Prerequisites & Configuration

For the board to stream reliably, the following Android properties should be configured:

```sh
# 1. Enable ADB over TCP (Port 5555)
setprop service.adb.tcp.port 5555
stop adbd && start adbd

# 2. Set SELinux to Permissive (Prevents binder SurfaceComposer permission drops)
setenforce 0

# 3. Disable Wi-Fi Sleep Policy (Prevents DTIM sleep when idle)
settings put global wifi_sleep_policy 2

# 4. Prevent Screen Sleep
svc power stayon true
```

---

## 🖱️ GUI Controls & Usage Guide

```
+-----------------------------------------------------------------------------------------------+
| [◀ Back] [⌂ Home] [▢ Apps] [☰ Menu] [⚡ Power] [🔊 Vol+] [🔉 Vol-]  [🔄 Reconnect] [📋 Logs] [⚙ Settings] |
+-----------------------------------------------------------------------------------------------+
|                                                                                               |
|                                     Live Screen Canvas                                        |
|                                       (1280x720 HD)                                           |
|                                                                                               |
+-----------------------------------------------------------------------------------------------+
```

### Top Toolbar Buttons
- **`◀ Back`:** Sends Android Hardware Back (`KEYCODE_BACK`, 4).
- **`⌂ Home`:** Returns to Android Home Screen (`KEYCODE_HOME`, 3).
- **`▢ Apps`:** Opens Recent Applications Switcher (`KEYCODE_APP_SWITCH`, 187).
- **`☰ Menu`:** Opens Context/Options Menu (`KEYCODE_MENU`, 82).
- **`⚡ Power / Unlock`:** Sends Wakeup (`KEYCODE_POWER`, 26), unlocks keyguard, and forces SurfaceFlinger draw.
- **`🔊 Vol +` / `🔉 Vol -`:** Adjusts audio master volume (`KEYCODE_VOLUME_UP` 24 / `KEYCODE_VOLUME_DOWN` 25).
- **`🔄 Reconnect`:** Resets socket stream and re-establishes minicap connection without restarting the application.
- **`📋 Logs`:** Opens the live, millisecond-precision log file (`NanoPiViewer.log`) in default text editor.
- **`⚙ Settings`:** Opens the live configuration dialog.

### Mouse & Touch Interaction
- **Left Click:** Injects an instant single touch (`input tap X Y`).
- **Left Click + Drag:** Calculates vector displacement and duration to perform natural swipe/drag gestures (`input swipe X1 Y1 X2 Y2 Duration`).
- **Right Click:** Short-cut for Hardware Back.
- **Middle Click (Wheel Click):** Short-cut for Home button.

### Keyboard Typing & Navigation
- **Alphanumeric Keys:** Typed characters are converted into direct Android text injection (`input text "..."`).
- **Special Keys:** `Enter` (Submit/Enter), `Backspace` (Delete), `Escape` (Back), `Tab` (Next Field), `Arrow Keys` (DPAD Navigation).

---

## ⚙️ Configuration Options (`config.json`)

Configuration is persisted in `config.json` next to the executable:

```json
{
  "device_ip": "192.168.1.113",
  "adb_port": 5555,
  "minicap_port": 1717,
  "native_resolution": "1280x720",
  "stream_resolution": "1280x720",
  "auto_connect": true,
  "keep_screen_on": true,
  "fps_limit": 60,
  "window_width": 1020,
  "window_height": 660
}
```

- **`device_ip`:** IPv4 address of the NanoPi 2 on Wi-Fi or Ethernet.
- **`adb_port`:** Port where `adbd` is listening on the device (default: `5555`).
- **`minicap_port`:** Localhost port forwarded to the `localabstract:minicap` socket (default: `1717`).
- **`native_resolution`:** Physical framebuffer geometry (`<width>x<height>`, default `1280x720`).
- **`stream_resolution`:** Target encoded stream geometry. Downscaling (e.g. `854x480`) can be used to reduce bandwidth on weak Wi-Fi networks.
- **`keep_screen_on`:** Automatically executes `svc power stayon true` on connection.

---

## 📦 Project Structure

```
NanoPiViewer/
├── assets/
│   ├── adb.exe               # Standalone Android Debug Bridge binary
│   ├── AdbWinApi.dll         # Windows ADB API library
│   ├── AdbWinUsbApi.dll      # Windows WinUSB API library
│   ├── minicap               # OpenSTF native capture daemon (ARMv7-a)
│   └── minicap.so            # OpenSTF SurfaceFlinger hook (Android 5.1 / SDK 22)
├── config.py                 # Configuration loader & persistent JSON manager
├── ui_settings.py            # Settings dialog GUI (Tkinter)
├── main.py                   # Main GUI viewer, input event router & socket stream engine
├── requirements.txt          # Python dependencies
└── README.md                 # Project documentation
```

---

## 🚀 Building & Running from Source

### Prerequisites
- Python 3.10+ (or [uv](https://github.com/astral-sh/uv))
- Windows 10 / 11 (x64)

### 1. Setup Environment
```bash
git clone https://github.com/Naloger/NanoPiViewer.git
cd NanoPiViewer

# Using uv (Recommended)
uv venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Run Directly
```bash
python main.py
```

### 3. Build Standalone Portable EXE
```bash
pyinstaller --noconsole --onefile --name "NanoPiViewer" --clean main.py
xcopy /E /I assets dist\assets
```
The standalone executable will be generated at `dist/NanoPiViewer.exe`.

---

## 📋 Troubleshooting & Diagnostics

If the viewer does not connect or freezes:
1. Click **`📋 Logs`** on the top toolbar to inspect the millisecond-precision log output (`NanoPiViewer.log`).
2. Verify that the device IP is reachable: `ping <device_ip>`.
3. Verify that ADB is listening on port 5555: `adb connect <device_ip>:5555`.
4. Ensure SELinux is set to `Permissive` on the board: `setenforce 0`.

---

## 📄 License
This project is licensed under the [MIT License](LICENSE).
