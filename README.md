# Aegis Download Manager

A clean, modular, and high-performance desktop download manager built with **PyQt6**, **aria2c**, and **yt-dlp**.

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
- **Native Browser Integration:** Independent Chrome and Edge extension powered by Native Messaging and Windows Named Pipe IPC (`\\.\pipe\Aegis_Download_Manager_Pipe`).
- **Pure Local Persistence:** SQLite database tracks download history and settings locally in `%APPDATA%\AegisDownloadManager\aegis_downloads.db`.
- **Zero Licensing Overhead:** Completely offline-first with no remote licensing calls, expiration dates, or HWID checks.
- **Headless CLI Mode:** Run `python main.py --download <url> --dest <folder>` (or the packaged `.exe`) to queue downloads without launching the GUI.

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
The application automatically checks for `aria2c.exe` and `ffmpeg.exe`:
- If in system `PATH`, Aegis detects them automatically.
- Alternatively, configure custom paths in **Settings (⚙)** in the UI.
- If `aria2c` is absent, Aegis automatically falls back to its built-in chunked HTTP downloader.

### 3. Run the Application
```bash
python main.py
```

---

## Browser Extension Installation (Chrome & Edge)

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
