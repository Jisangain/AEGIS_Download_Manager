# Aegis Download Manager

Aegis is a desktop download manager built with Python and PyQt6. It provides a download queue, aria2 and HTTP download engines, yt-dlp media downloads, scheduling, archive extraction, checksums, and an optional browser extension that sends links to the desktop app.

## Download

- **Windows:** [Download the v1.0.0 executable](https://github.com/jaberDevHub/AEGIS_Download_Manager/releases/download/v1.0.0/Aegis.Download.Manager.exe)
- [All GitHub releases](https://github.com/jaberDevHub/AEGIS_Download_Manager/releases)
- **Linux:** No prebuilt Linux release is currently documented; build from source below.

The browser extension is distributed in the repository under `browser_extension/`, not in the Windows executable.

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

On Windows, run `build_exe.bat`. On Linux, create and activate a virtual environment, install the application requirements and PyInstaller, then run `bash build_linux.sh`. The Linux script creates the application and extension package under `dist/linux-package/`. See the scripts for build prerequisites and output details.

## Browser extension

1. Keep the repository or extracted package in a permanent folder.
2. In the browser’s extensions page, enable developer mode and load `browser_extension/` as an unpacked extension (in a Linux package, use `dist/linux-package/browser_extension/`).
3. On Windows, run `browser_extension/install_host.bat` after loading the extension. On Linux, run `install_host_linux.sh` from the packaged extension directory and provide the extension ID shown by the browser.
4. Restart the browser. Keep Aegis running to accept browser requests.

## Tests

Run the focused security regression tests and existing feature checks from the repository root:

```bash
python -m unittest test_security -v
python test_new_features.py
python test_file_management_automation.py
```

## Security

A limited source review and focused regression tests have been performed; this is not a complete penetration test or independent security audit. See [SECURITY.md](SECURITY.md) for the audit scope, verified fixes, reporting guidance, and known limitations.
