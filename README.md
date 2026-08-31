# 📱 NanoPiViewer

High-performance, low-latency, portable screen streaming and remote control application for **FriendlyARM NanoPi 2** (Samsung S5P4418 / Android 5.1 Lollipop) and similar embedded Android boards.

---

## ✨ Features

- **🚀 Sub-50ms Ultra-Low Latency:** Powered by **OpenSTF `minicap`** native SurfaceFlinger frame capture with hardware SIMD JPEG compression.
- **🖥️ Crystal-Clear HD Resolution:** Supports native 1280x720 160 DPI display scaling with bilinear filtering.
- **🖱️ Full Mouse & Touch Emulation:**
  - **Left Click:** Tap
  - **Left Click + Drag:** Swipe / Drag
  - **Right Click:** Android Hardware Back
  - **Middle Click:** Android Home Button
  - **Keyboard:** Direct text typing and navigation keys (Arrow keys, Enter, Backspace, Esc).
- **⚙️ Configurable & Portable:**
  - Customizable IP, ADB Port, Minicap Port, Resolutions, and Stay-Awake toggles.
  - Interactive **Settings GUI** dialog.
  - Standalone single executable (PyInstaller) with self-contained assets.
- **📋 Live Diagnostics & Logging:** Real-time millisecond-precision logger writing to `NanoPiViewer.log` with a one-click "📋 Logs" viewer.

---

## 🛠️ Project Structure

```
NanoPiViewer/
├── assets/
│   ├── adb.exe               # Standalone Android Debug Bridge binary
│   ├── AdbWinApi.dll
│   ├── AdbWinUsbApi.dll
│   ├── minicap               # OpenSTF native capture daemon (armeabi-v7a)
│   └── minicap.so            # OpenSTF SurfaceFlinger hook (API 22)
├── config.py                 # Configuration manager (config.json)
├── ui_settings.py            # Settings dialog GUI
├── main.py                   # Main GUI application & stream engine
├── requirements.txt          # Python dependencies
└── README.md                 # Documentation
```

---

## 🚀 Getting Started

### Prerequisites
- Python 3.10+ (or [uv](https://github.com/astral-sh/uv))
- Windows 10/11

### 1. Clone the Repository
```bash
git clone https://github.com/Naloger/NanoPiViewer.git
cd NanoPiViewer
```

### 2. Setup Virtual Environment & Dependencies
```bash
uv venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Run Directly
```bash
python main.py
```

### 4. Build Standalone Portable Executable
```bash
pyinstaller --noconsole --onefile --name "NanoPiViewer" --clean main.py
xcopy /E /I assets dist\assets
```
The resulting executable will be available in `dist/NanoPiViewer.exe`.

---

## 📄 License
MIT License
