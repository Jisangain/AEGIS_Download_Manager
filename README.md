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
- `aria2c` is optional; without it, Aegis has a built-in HTTP downloader. `ffmpeg` is optional and is used for yt-dlp media merging and audio conversion.
- The browser integration supports Chromium-based browsers with native messaging. The extension requests broad site access to detect and hand off media/download links; review its permissions before enabling it.

## Run from source

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

On Windows, run `build_exe.bat`. It builds the app and creates `dist/Aegis-Browser-Extension.zip` for publishing as a separate GitHub Release asset. On Linux, create and activate a virtual environment, install the application requirements and PyInstaller, then run `bash build_linux.sh`. The Linux script creates the application and extension package under `dist/linux-package/`. See the scripts for build prerequisites and output details.

## Browser extension

1. Download and extract the **Aegis Browser Extension ZIP** release asset to a permanent folder.
2. In Chrome, Brave, or Edge, open the extensions page, enable developer mode, and load the extracted folder containing `manifest.json` as unpacked.
3. Copy the extension ID shown on its card, then run `install_host.bat` from the extracted folder and paste the ID when prompted. This registers the bundled native host; Python is not required.
4. Restart the browser and launch Aegis. Keep the extracted folder in the same location after setup.

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
