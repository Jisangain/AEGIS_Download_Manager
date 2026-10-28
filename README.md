# Aegis Download Manager

A clean, modular, and high-performance desktop download manager built with **PyQt6**, **aria2c**, and **yt-dlp**. The Python app supports Windows and Linux; platform installers are built separately on each operating system.

## Direct Download

- **Windows 64-bit:** [Download the latest Aegis executable](https://github.com/jaberDevHub/AEGIS---Download-Manager/releases/latest/download/Aegis-Download-Manager.exe) (standalone `.exe`)
- [Browse all GitHub releases](https://github.com/jaberDevHub/AEGIS---Download-Manager/releases)
- **Linux:** Build from source using the [Linux instructions](#linux-build-and-browser-integration). A prebuilt Linux download is not available yet.

The direct Windows link works after a GitHub Release has been published with an asset named exactly `Aegis-Download-Manager.exe`.

### Publish a Windows download

1. Build the executable on Windows with `build_exe.bat`.
2. Open the repository’s [Releases page](https://github.com/jaberDevHub/AEGIS---Download-Manager/releases) and choose **Draft a new release**.
3. Create a tag such as `v1.0.0`, enter a release title and notes, and attach `dist\Aegis Download Manager.exe`.
4. Rename the built file to `Aegis-Download-Manager.exe` before uploading it, so the README’s direct download link matches.
5. Publish the release. GitHub will serve the attached executable through the direct link above; no website deployment is needed.

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

## Browser Extension: Download, Install, and Use

The browser extension is included in the source repository under `browser_extension/`; it is not a separate download in the Windows `.exe` release. Keep the extracted repository folder in a permanent location because the native host runs from that folder.

### Windows (Chrome, Edge, or Brave)

1. Download the repository as a ZIP: open the GitHub repository, choose **Code → Download ZIP**, and extract it somewhere permanent (for example, `C:\Apps\AegisDownloadManager`).
2. Install and open Aegis Download Manager. Leave it running while sending downloads from the browser.
3. In the extracted folder, run `browser_extension\install_host.bat`. Administrator access is not normally needed; the script registers the native messaging host for your Windows user. Keep the extracted folder where it is after installation.
4. Open your browser’s extension page: `chrome://extensions`, `edge://extensions`, or `brave://extensions`.
5. Turn on **Developer mode**, click **Load unpacked**, and select the extracted `browser_extension` folder.
6. If the extension does not appear immediately, restart the browser.

To use it, right-click a link and choose **Download with Aegis**. For supported media, right-click the media and choose **Download Media with Aegis**; to pass the current page, right-click the page and choose **Download Page / Video with Aegis**. Aegis must be running to receive the request.

### Linux (Chrome, Chromium, Brave, or Edge)

Build the Linux package first using the instructions below. Then:

1. Run `dist/linux-package/aegis-download-manager` once.
2. Open the browser’s extensions page, enable **Developer mode**, choose **Load unpacked**, and select `dist/linux-package/browser_extension/`.
3. Copy the extension ID shown on the extension card.
4. Run the native host installer with that ID:

   ```bash
   bash dist/linux-package/browser_extension/install_host_linux.sh YOUR_EXTENSION_ID
   ```

5. Restart the browser and leave Aegis running when using **Download with Aegis** from the right-click menu.

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
