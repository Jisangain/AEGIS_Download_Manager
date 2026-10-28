# Aegis Download Manager

A clean, modular, and high-performance desktop download manager built with **PyQt6**, **aria2c**, and **yt-dlp**. The Python app supports Windows and Linux; platform installers are built separately on each operating system.

inux:** Build from source using the [Linux instructions](#linux-build-and-browser-integration). A prebuilt Linux download is not available yet.

Designed as a zero-telemetry, zero-backend, fully independent alternative without trial countdowns, activation servers, or licensing restrictions.

---

## Key Features

- **Extreme Multi-Connection Acceleration:** Supports multi-threaded segmented downloads (up to 32 connections per file) powered by `aria2c`.
- **Media & Video Extraction:** Built-in `yt-dlp` integration for seamless downloading and format selection (1080p, 720p, 480p, MP3/Audio) across 1,000+ streaming sites.
- **FFmpeg Post-Processing:** Automatically merges separate adaptive video and audio streams into standard MP4/MKV files and extracts MP3 audio tracks.
- **Batch URL Import (.txt):** Import lists of URLs from text files with real-time validation, automatic filename extraction, item preview checkboxes, and one-click queueing.
- **Download Speed Limiter:** Configurable bandwidth throttle (in KB/s or unlimited) passed directly to `aria2c` (`--max-download-limit`), `yt-dlp` (`ratelimit`), and `DirectHttpWorker` (chunk throttling).
- **Clipboard Monitoring:** Optional link sniffer that detects copied HTTP/HTTPS links and prompts the user before queueing (never downloads automatically without user confirmation).
- **Scheduled Downloads:** Schedule queued downloads to start automatically at a specified date and time. Schedules persist across application restarts.
- **Native Browser Integration:** Chrome, Chromium, Brave, and Edge extension integration using native messaging, Windows Named Pipes, or a per-user Unix domain socket.
- **Pure Local Persistence:** SQLite stores history and settings under `%APPDATA%\AegisDownloadManager` on Windows and `${XDG_CONFIG_HOME:-~/.config}/AegisDownloadManager` on Linux.
- **Zero Licensing Overhead:** Completely offline-first with no remote licensing calls, expiration dates, or HWID checks.
- **Headless CLI Mode:** Run `python main.py --download <url> --dest <folder>` (or the packaged `.exe`) to queue downloads without launching the GUI. Supports `--format <id>`, `--audio-only`, `--timeout <seconds>` and `--help`.

---

## Directory Structure

```
AegisDownloadManager/
├── main.py                     # Application entry point (GUI + CLI automation mode)
├── ui.py                       # Modern PyQt6 user interface, dialogs, and styling
├── engine.py                   # Workers (Aria2Worker, YtDlpWorker, DirectHttpWorker)
├── database.py                 # SQLite database & configuration manager
├── ipc_server.py               # Named pipe IPC server for browser integration
├── aegis_host.py               # Native Messaging host bridge for Chrome & Edge
├── build_exe.bat               # Standalone Windows executable packager
├── build_linux.sh              # Standalone Linux executable packager
├── ipc_transport.py            # Cross-platform IPC client for the app and browser host
├── platform_paths.py           # Per-platform application data paths
├── validate_e2e.py             # Full end-to-end regression validation test suite
├── test_new_features.py        # Automated test suite for new features
├── requirements.txt            # Python dependencies
└── browser_extension/          # Independent Chrome/Edge extension
    ├── manifest.json           # Manifest V3 extension configuration
    ├── background.js           # Context menu & download capture worker
    ├── com.aegis.downloadmanager.json  # Native messaging host definition
    ├── aegis_host.bat          # Native messaging host launcher
    ├── install_host.bat        # Host registration script for Chrome/Edge
    └── uninstall_host.bat      # Host cleanup script
```

---

## Setup & Running from Source

### Prerequisites
- Python 3.10+
- PyQt6
- yt-dlp

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. External Tools
The application automatically checks for `aria2c` and `ffmpeg` (use `.exe` versions on Windows):
- If in system `PATH`, Aegis detects them automatically on both platforms.
- Alternatively, configure custom paths in **Settings (⚙)** in the UI.
- If `aria2c` is absent, Aegis automatically falls back to its built-in chunked HTTP downloader.

### 3. Run the Application
```bash
python main.py
```

---

## Browser Extension Installation on Windows

Aegis includes an independent Manifest V3 browser extension and a native messaging host that forwards browser downloads to Aegis via a local Windows Named Pipe (`\\.\pipe\Aegis_Download_Manager_Pipe`).

### Step 1: Register the Native Host
Run as Administrator or regular user:
```cmd
browser_extension\install_host.bat
```
This registers `com.aegis.downloadmanager` in the Windows Registry under:
- `HKCU\Software\Google\Chrome\NativeMessagingHosts\com.aegis.downloadmanager`
- `HKCU\Software\Microsoft\Edge\NativeMessagingHosts\com.aegis.downloadmanager`

### Step 2: Load Extension in Browser
1. In Google Chrome or Microsoft Edge, navigate to `chrome://extensions` or `edge://extensions`.
2. Toggle on **Developer Mode** (top right corner).
3. Click **Load unpacked**.
4. Select the `AegisDownloadManager/browser_extension` folder.
5. Right-click any link, video, or page in the browser and choose **Download with Aegis**.

## Linux Build and Browser Integration

Build Linux packages on a Linux machine. PyInstaller does not cross-compile the Windows build:

```bash
sudo apt install python3 python3-venv python3-pip libgl1 libegl1 libxcb-cursor0 aria2 ffmpeg
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt pyinstaller
bash build_linux.sh
```

The app binary and browser extension package are created under `dist/linux-package/`. Run `dist/linux-package/aegis-download-manager` to launch the app. `aria2` and `ffmpeg` are optional; without `aria2`, Aegis falls back to its built-in HTTP downloader. FFmpeg is needed for yt-dlp media merging and audio extraction.

To enable browser integration, load `dist/linux-package/browser_extension/` as an unpacked extension, copy its 32-character extension ID from the browser's Extensions page, then run:

```bash
bash dist/linux-package/browser_extension/install_host_linux.sh YOUR_EXTENSION_ID
```

The installer registers the native messaging host for Chrome, Chromium, Brave, and Edge under the current user's home directory. Restart the browser after installing it.

Windows Defender scanning is available only on Windows. Other download, queue, archive extraction, checksum, scheduling, and media features use the shared Python app.

---

## Standalone Windows Executable (.exe)

Compile Aegis into a single standalone Windows executable without console popups:

```cmd
build_exe.bat
```

The resulting executable is generated at:
`dist\Aegis Download Manager.exe`

### Automated CLI Download Testing with Packaged Binary
```cmd
"dist\Aegis Download Manager.exe" --download https://example.com/file.zip --dest ./downloads
```
