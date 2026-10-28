# Aegis Download Manager

Aegis is a desktop download manager built with Python and PyQt6. It provides a download queue, aria2 and HTTP download engines, yt-dlp media downloads, scheduling, archive extraction, checksums, and an optional browser extension that sends links to the desktop app.

## Download

- **Windows:** [Download the v1.0.0 executable](https://github.com/jaberDevHub/AEGIS_Download_Manager/releases/download/v1.0.0/Aegis.Download.Manager.exe)
- [All GitHub releases](https://github.com/jaberDevHub/AEGIS_Download_Manager/releases)
- **Linux:** No prebuilt Linux release is currently documented; build from source below.

The Windows browser integration needs a native messaging host executable. Download the [Aegis Browser Extension ZIP release asset](https://github.com/jaberDevHub/AEGIS_Download_Manager/releases/latest/download/Aegis-Browser-Extension.zip); the GitHub **Code → Download ZIP** source archive does not include that executable. The extension bundle runs without Python installed. The link works after this ZIP is attached to a GitHub release.

## Repository layout

- Application modules and platform build scripts stay at the repository root because the build scripts reference them there.
- `browser_extension/` contains the browser integration; `frontend/` contains the separate Electron prototype.
- `tests/` contains test and validation scripts, with visual test assets in `tests/assets/`.
- `docs/audits/` contains the earlier detailed audit report. The current security overview is [SECURITY.md](SECURITY.md).

## Requirements

- Windows or Linux for the desktop application; build each packaged version on its target operating system.
- Python 3.10 or newer to run from source.
- `aria2c` is optional; without it, Aegis has a built-in HTTP downloader. FFmpeg is required to merge separate video and audio streams, which YouTube commonly uses for 1080p and higher. If FFmpeg is missing, Aegis reports the requirement instead of silently switching to a lower-quality stream. Install FFmpeg and set its executable path in Settings (or make it available on `PATH`). The Windows build bundles QuickJS-NG and yt-dlp’s EJS challenge support, so users do not need Python or a JavaScript runtime separately.
- The browser integration supports Chromium-based browsers with native messaging. The extension requests broad site access to detect and hand off media/download links; review its permissions before enabling it.

## Run from source

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
├── setup_windows.bat           # Installs Python, project dependencies, and FFmpeg, then launches Aegis
├── build_exe.bat               # Standalone Windows executable packager
├── build_linux.sh              # Standalone Linux executable packager
├── ipc_transport.py            # Cross-platform IPC client for the app and browser host
├── platform_paths.py           # Per-platform application data paths
├── tests/                      # Automated test and validation scripts
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

### Windows: fresh setup
From the extracted repository folder, double-click `setup_windows.bat`. It uses an existing Python 3.10+ installation or downloads the SHA-256-verified Python 3.13.17 installer, creates a project virtual environment, downloads and verifies FFmpeg into `tools/`, installs `requirements.txt`, and launches Aegis. The FFmpeg archive is about 109 MB. It does not require administrator access. Internet access is needed for first setup.

### Linux or manual setup

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
python -m pip install -r requirements.txt
python main.py
```

For CLI use:

```bash
python main.py --download "https://example.com/file.zip" --dest ./downloads
```

Use `python main.py --help` for supported options. The requirements file specifies minimum versions rather than a fully pinned environment.

### Build

On Windows, install `requirements.txt` and PyInstaller, then run `build_exe.bat`. It builds the app with yt-dlp’s default YouTube challenge components and the bundled QuickJS-NG runtime, and creates `dist/Aegis-Browser-Extension.zip` for publishing as a separate GitHub Release asset. On Linux, create and activate a virtual environment, install the application requirements and PyInstaller, then run `bash build_linux.sh`. The Linux script creates the application and extension package under `dist/linux-package/`. See the scripts for build prerequisites and output details.

## Browser extension

1. Download and extract the **Aegis Browser Extension ZIP** release asset to a permanent folder.
2. In Chrome, Brave, or Edge, open the extensions page, enable developer mode, and load the extracted folder containing `manifest.json` as unpacked.
3. Run `install_host.bat` from that same folder. It detects the loaded extension automatically and registers the bundled native host; you do not need to copy or type an extension ID, and Python is not required.
4. Restart the browser and launch Aegis. Keep the extracted folder in the same location after setup.

Chromium requires unpacked extensions to be loaded through the browser’s extensions page. If Aegis reports a host authorization or missing-host error, run `install_host.bat` again from the folder you loaded, then restart the browser.

For Linux source builds, load `dist/linux-package/browser_extension/` and run its `install_host_linux.sh` with the extension ID. Linux native-host setup requires Python 3.

## Tests

Test and validation scripts are grouped in `tests/`. Run the focused security regression tests and existing feature checks from the repository root:

```bash
python -m unittest tests.test_security -v
python -m tests.test_new_features
python -m tests.test_file_management_automation
```

## Security

A limited source review and focused regression tests have been performed; this is not a complete penetration test or independent security audit. See [SECURITY.md](SECURITY.md) for the audit scope, verified fixes, reporting guidance, and known limitations.
