# Aegis Download Manager

Aegis is a desktop download manager built with Python and PyQt6. It provides a download queue, aria2 and HTTP download engines, yt-dlp media downloads, scheduling, archive extraction, checksums, and an optional browser extension that sends links to the desktop app.

The Windows browser integration uses a native messaging host executable. The [Aegis Browser Extension ZIP release asset](https://github.com/jaberDevHub/AEGIS_Download_Manager/releases/latest/download/Aegis-Browser-Extension.zip) includes it. The executable is also included in GitHub **Code → Download ZIP**. If you use an older source archive without it, `install_host.bat` downloads the host from this repository. Python is not required.

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

## Install on Windows

Install [Git for Windows](https://git-scm.com/download/win), then open Command Prompt or PowerShell and run:

```powershell
git clone https://github.com/jaberDevHub/AEGIS_Download_Manager.git
cd AEGIS_Download_Manager
.\setup_windows.bat
```

The setup script installs or locates Python, downloads FFmpeg, installs the required packages, and launches Aegis. Keep an internet connection during setup.

To update later, open the project folder and run `git pull --ff-only origin main`, then run `setup_windows.bat` again.

## Run from source on Linux

Install Python 3.10+, then run:

```bash
python3 -m pip install -r requirements.txt
python3 main.py
```

FFmpeg is needed to merge separate high-resolution video and audio streams. Install it with your Linux package manager if it is not already available.

For CLI use:

```bash
python main.py --download "https://example.com/file.zip" --dest ./downloads
```

Use `python main.py --help` for supported options. The requirements file specifies minimum versions rather than a fully pinned environment.

### Build

On Windows, install `requirements.txt` and PyInstaller, then run `build_exe.bat`. It builds the app with yt-dlp’s default YouTube challenge components and the bundled QuickJS-NG runtime, and creates `dist/Aegis-Browser-Extension.zip` for publishing as a separate GitHub Release asset. On Linux, create and activate a virtual environment, install the application requirements and PyInstaller, then run `bash build_linux.sh`. The Linux script creates the application and extension package under `dist/linux-package/`. See the scripts for build prerequisites and output details.

## Browser extension

1. Download and extract the **Aegis Browser Extension ZIP** release asset to a permanent folder.
2. Run `install_host.bat` from that folder. It opens the browser extensions page and waits while you enable Developer mode and choose **Load unpacked** for that same folder.
3. The installer detects the extension ID and registers the bundled native host automatically. Keep its window open until it reports completion; no ID copying, second installer run, or Python installation is needed.
4. Restart the browser, launch Aegis, and click the extension icon to see its automatic connection check. Keep the extracted folder in the same location.

Chromium requires a user to load unpacked extensions in Developer mode. If Aegis reports a host authorization or missing-host error, run `install_host.bat` again from the extracted folder, then restart the browser. Installing directly from the browser store would remove the unpacked-extension step; that requires publishing Aegis in each browser’s extension store.

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
