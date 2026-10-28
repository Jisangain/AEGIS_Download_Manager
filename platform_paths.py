"""Small platform-aware paths shared by the desktop app and browser host."""

import os
import sys


def app_data_directory() -> str:
    """Return Aegis's per-user writable data directory."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.join(
            os.path.expanduser("~"), "AppData", "Roaming"
        )
    elif sys.platform == "darwin":
        base = os.path.join(os.path.expanduser("~"), "Library", "Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(
            os.path.expanduser("~"), ".config"
        )
    path = os.path.join(base, "AegisDownloadManager")
    os.makedirs(path, exist_ok=True)
    return path

