"""
Aegis Download Manager - Main Entry Point
Independent, high-speed, zero-license download manager.
"""

import sys
import os
import time
import json
import urllib.parse
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from ui import MainWindow

def attach_console_if_needed():
    if sys.platform == "win32" and (sys.stdout is None or sys.stderr is None):
        try:
            import ctypes
            if ctypes.windll.kernel32.AttachConsole(-1):
                if sys.stdout is None:
                    sys.stdout = open("CONOUT$", "w")
                if sys.stderr is None:
                    sys.stderr = open("CONOUT$", "w")
        except Exception:
            pass

def run_cli_download(url: str, dest_dir: str, format_id: str = "", audio_only: bool = False, timeout: int = 120) -> int:
    from engine import Aria2Worker, DirectHttpWorker, YtDlpWorker, find_tool_binary

    app = QApplication.instance()
    dest = os.path.abspath(dest_dir)
    os.makedirs(dest, exist_ok=True)

    parsed = urllib.parse.urlparse(url)
    raw_name = os.path.basename(parsed.path) or "downloaded_file.bin"
    if audio_only and not raw_name.endswith(".mp3"):
        raw_name = os.path.splitext(raw_name)[0] + ".mp3"

    res = {"status": "pending", "file": None, "error": None}
    done = [False]

    is_youtube = "youtube.com" in url.lower() or "youtu.be" in url.lower()
    aria2_bin = find_tool_binary("aria2c")

    format_to_use = format_id
    if audio_only and not format_to_use:
        format_to_use = "bestaudio/best"

    if is_youtube:
        worker = YtDlpWorker(1, url, raw_name, dest, format_id=format_to_use)
    elif aria2_bin:
        worker = Aria2Worker(1, url, raw_name, dest)
    else:
        worker = DirectHttpWorker(1, url, raw_name, dest)

    def on_status(tid, status, msg):
        if status == "completed":
            res["status"] = "completed"
            done[0] = True
        elif status == "failed":
            res["status"] = "failed"
            res["error"] = msg
            done[0] = True

    def on_finished(tid, path):
        res["file"] = path

    worker.status_signal.connect(on_status)
    worker.finished_signal.connect(on_finished)
    worker.start()

    start_t = time.time()
    while not done[0] and (time.time() - start_t) < timeout:
        app.processEvents()
        time.sleep(0.05)

    worker.wait(5000)

    result_path = os.path.join(dest, "aegis_cli_result.json")
    try:
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump(res, f, indent=2)
    except Exception:
        pass

    if res["status"] == "completed":
        print(f"DOWNLOAD_SUCCESS: {res.get('file')}")
        return 0
    else:
        print(f"DOWNLOAD_FAILED: {res.get('error')}")
        return 1

def main():
    attach_console_if_needed()
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("aegis.downloadmanager.app.1")
        except Exception:
            pass
    app = QApplication(sys.argv)
    app.setApplicationName("Aegis Download Manager")
    app.setOrganizationName("Aegis")

    from ui import DARK_STYLESHEET
    from PyQt6.QtGui import QPalette, QColor, QIcon
    dark_pal = QPalette()
    dark_pal.setColor(QPalette.ColorRole.Window, QColor("#18181B"))
    dark_pal.setColor(QPalette.ColorRole.WindowText, QColor("#F8FAFC"))
    dark_pal.setColor(QPalette.ColorRole.Base, QColor("#242429"))
    dark_pal.setColor(QPalette.ColorRole.AlternateBase, QColor("#1E1E23"))
    dark_pal.setColor(QPalette.ColorRole.ToolTipBase, QColor("#2D2D34"))
    dark_pal.setColor(QPalette.ColorRole.ToolTipText, QColor("#FFFFFF"))
    dark_pal.setColor(QPalette.ColorRole.Text, QColor("#F8FAFC"))
    dark_pal.setColor(QPalette.ColorRole.Button, QColor("#242429"))
    dark_pal.setColor(QPalette.ColorRole.ButtonText, QColor("#F8FAFC"))
    dark_pal.setColor(QPalette.ColorRole.BrightText, QColor("#38BDF8"))
    dark_pal.setColor(QPalette.ColorRole.Highlight, QColor("#007AFF"))
    dark_pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
    app.setPalette(dark_pal)
    app.setStyleSheet(DARK_STYLESHEET)

    # Set application & taskbar icon
    base_dir = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    icon_name = "icon.ico" if sys.platform == "win32" else "icon.png"
    icon_path = os.path.join(base_dir, icon_name)
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    # CLI / Automation mode
    if "--help" in sys.argv or "-h" in sys.argv:
        print(
            "Aegis Download Manager - CLI Mode\n"
            "Usage: python main.py --download <url> [--dest <folder>] [--format <id>] "
            "[--audio-only] [--timeout <seconds>]\n"
            "  --download     URL to download\n"
            "  --dest         Destination folder (default: current directory)\n"
            "  --format       yt-dlp format id (e.g. 1080p, bestaudio/best)\n"
            "  --audio-only   Extract audio only (MP3)\n"
            "  --timeout      Maximum seconds to wait (default: 120)\n"
        )
        sys.exit(0)

    if "--download" in sys.argv:
        idx = sys.argv.index("--download")
        if idx + 1 < len(sys.argv):
            target_url = sys.argv[idx + 1]
            dest = "."
            if "--dest" in sys.argv:
                d_idx = sys.argv.index("--dest")
                if d_idx + 1 < len(sys.argv):
                    dest = sys.argv[d_idx + 1]
            audio_only = "--audio-only" in sys.argv
            fmt = ""
            if "--format" in sys.argv:
                f_idx = sys.argv.index("--format")
                if f_idx + 1 < len(sys.argv):
                    fmt = sys.argv[f_idx + 1]
            timeout = 120
            if "--timeout" in sys.argv:
                t_idx = sys.argv.index("--timeout")
                if t_idx + 1 < len(sys.argv):
                    try:
                        timeout = max(1, int(sys.argv[t_idx + 1]))
                    except ValueError:
                        pass
            sys.exit(run_cli_download(target_url, dest, format_id=fmt, audio_only=audio_only, timeout=timeout))

    # IDM-compatible /d, -d, --url arguments
    url_to_add = None
    fn_to_add = None
    fmt_to_add = None
    for i, arg in enumerate(sys.argv):
        if arg in ("/d", "-d", "--url") and i + 1 < len(sys.argv):
            url_to_add = sys.argv[i + 1]
        elif arg in ("/f", "-f", "--filename") and i + 1 < len(sys.argv):
            fn_to_add = sys.argv[i + 1]
        elif arg in ("/format", "--format") and i + 1 < len(sys.argv):
            fmt_to_add = sys.argv[i + 1]

    from ipc_server import send_ipc_message
    if url_to_add:
        msg = {
            "action": "download",
            "url": url_to_add,
            "filename": fn_to_add or "",
            "format_id": fmt_to_add or ""
        }
        res = send_ipc_message(msg, timeout_ms=1000)
        if res and res.get("status") == "ok":
            sys.exit(0)
    else:
        # Single instance check: bring existing instance to foreground if already running
        res = send_ipc_message({"action": "bring_to_front"}, timeout_ms=400)
        if res and res.get("status") == "ok":
            sys.exit(0)

    window = MainWindow()
    window.showMaximized()

    if url_to_add:
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(200, lambda: window._on_browser_ipc_message(msg))

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
