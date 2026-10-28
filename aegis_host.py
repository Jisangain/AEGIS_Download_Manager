"""
Aegis Download Manager - Native Messaging Host
Bridges Chrome, Brave, and Edge browser extensions to the Aegis desktop application.
Ensures reliable delivery, cold-start launching, race-condition mitigation, and acceptance confirmation.
Pure standard library, zero third-party dependencies.
"""

import sys
import os
import struct
import json
import time
import subprocess
import shutil
from datetime import datetime
from typing import Optional, Dict, Any

from ipc_transport import send_ipc_message, PIPE_NAME
from platform_paths import app_data_directory

if sys.platform == "win32":
    import msvcrt
    import ctypes
    from ctypes import wintypes
    try:
        msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
        msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
    except Exception:
        pass
    kernel32 = ctypes.windll.kernel32
else:
    kernel32 = None

def log_debug(msg: str):
    """Appends diagnostic information strictly to the log file, never stdout."""
    try:
        app_data = app_data_directory()
        with open(os.path.join(app_data, "aegis_host.log"), "a", encoding="utf-8") as f:
            f.write(f"{datetime.now().isoformat()} - [HOST] {msg}\n")
    except Exception:
        pass

def read_native_message() -> Optional[Dict[str, Any]]:
    """Reads a length-prefixed JSON message from the browser over stdin."""
    try:
        raw_length = sys.stdin.buffer.read(4)
        if len(raw_length) < 4:
            log_debug("Native message raw_length < 4 bytes (channel closed by browser)")
            return None
        message_length = struct.unpack("@I", raw_length)[0]
        if message_length <= 0 or message_length > 10 * 1024 * 1024:
            log_debug(f"Invalid message length: {message_length}")
            return None
        raw_data = sys.stdin.buffer.read(message_length)
        if len(raw_data) < message_length:
            log_debug(f"Truncated message: read {len(raw_data)} of {message_length} bytes")
            return None
        parsed = json.loads(raw_data.decode("utf-8"))
        log_debug(f"Received valid native message: action={parsed.get('action')}, url={parsed.get('url')}")
        return parsed
    except Exception as e:
        log_debug(f"Exception reading native message: {e}")
        return None

def send_native_response(payload: Dict[str, Any]):
    """Sends a length-prefixed JSON response back to the browser over stdout."""
    try:
        encoded = json.dumps(payload).encode("utf-8")
        sys.stdout.buffer.write(struct.pack("@I", len(encoded)))
        sys.stdout.buffer.write(encoded)
        sys.stdout.buffer.flush()
        log_debug(f"Dispatched native response to browser: {payload.get('status')}")
    except Exception as e:
        log_debug(f"Failed to write native response (browser pipe closed): {e}")

def validate_request(msg: Optional[Dict[str, Any]]) -> Optional[str]:
    """Validates the structure of the incoming browser message."""
    if not msg or not isinstance(msg, dict):
        return "Empty or malformed JSON payload"
    action = msg.get("action")
    if not action or action not in ("download", "ping", "bring_to_front"):
        return f"Unsupported or missing action: {action}"
    if action == "download":
        url = msg.get("url")
        if not url or not isinstance(url, str) or not url.strip():
            return "Missing or empty download URL"
        url_lower = url.strip().lower()
        if not (url_lower.startswith("http://") or url_lower.startswith("https://") or
                url_lower.startswith("ftp://") or url_lower.startswith("blob:") or
                url_lower.startswith("data:")):
            return f"Invalid URL scheme: {url[:30]}"
    return None

def find_aegis_executable() -> Optional[str]:
    """Locates the Aegis desktop application executable from installation or workspace paths."""
    # 1. Check Windows Registry (Installed Aegis)
    if sys.platform == "win32":
        try:
            import winreg
            for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                for subkey in (r"Software\AegisDownloadManager", r"Software\Wow6432Node\AegisDownloadManager"):
                    try:
                        with winreg.OpenKey(root, subkey) as k:
                            val, _ = winreg.QueryValueEx(k, "Path")
                            if val and os.path.isfile(val):
                                return os.path.abspath(val)
                    except Exception:
                        pass
        except Exception:
            pass

    # 2. Check path relative to native host binary
    if getattr(sys, "frozen", False):
        host_dir = os.path.dirname(os.path.abspath(sys.executable))
    else:
        host_dir = os.path.dirname(os.path.abspath(__file__))

    if sys.platform == "win32":
        application_names = ["Aegis Download Manager.exe"]
    else:
        application_names = ["aegis-download-manager", "Aegis Download Manager"]
    relative_candidates = [
        os.path.join(directory, name)
        for directory in (
            host_dir,
            os.path.join(host_dir, ".."),
            os.path.join(host_dir, "..", "dist"),
            os.path.join(host_dir, "dist"),
        )
        for name in application_names
    ]
    for cand in relative_candidates:
        norm = os.path.normpath(cand)
        if os.path.isfile(norm):
            return norm

    # 3. Development fallback (Python script)
    dev_candidates = [
        os.path.join(host_dir, "..", "main.py"),
        os.path.join(host_dir, "main.py"),
    ]
    for cand in dev_candidates:
        norm = os.path.normpath(cand)
        if os.path.isfile(norm):
            return norm

    if sys.platform != "win32":
        installed_app = shutil.which("aegis-download-manager")
        if installed_app:
            return os.path.abspath(installed_app)

    return None

def launch_aegis(executable_path: str) -> bool:
    """Launches the Aegis desktop application in a detached process."""
    log_debug(f"Launching desktop application: {executable_path}")
    try:
        if sys.platform == "win32" and not executable_path.lower().endswith(".py"):
            try:
                os.startfile(executable_path)
                log_debug("Launched Aegis via os.startfile successfully")
                return True
            except Exception as e_startfile:
                log_debug(f"os.startfile failed ({e_startfile}), falling back to Popen")

        if executable_path.lower().endswith(".py"):
            py_exe = sys.executable.replace("python.exe", "pythonw.exe")
            if not os.path.isfile(py_exe):
                py_exe = sys.executable
            cmd = [py_exe, executable_path]
        else:
            cmd = [executable_path]

        launch_options = {
            "cwd": os.path.dirname(executable_path),
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
            "close_fds": True,
        }
        if sys.platform == "win32":
            launch_options["creationflags"] = 0x00000208  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
        else:
            launch_options["start_new_session"] = True
        p = subprocess.Popen(cmd, **launch_options)
        log_debug(f"Spawned Aegis process with Popen (PID {p.pid})")
        return True
    except Exception as e:
        log_debug(f"Failed to launch Aegis process: {e}")
        return False

def main():
    log_debug("=== Native host invoked ===")
    msg = read_native_message()
    if not msg:
        sys.exit(0)

    # 1. Validate incoming request
    validation_err = validate_request(msg)
    if validation_err:
        log_debug(f"Validation failed: {validation_err}")
        send_native_response({"status": "error", "error": validation_err})
        sys.exit(0)

    if msg.get("action") == "ping":
        send_native_response({"status": "ok", "message": "Aegis native messaging host is reachable"})
        sys.exit(0)

    # 2. Fast Path: Check if Aegis is already running and responsive
    reply = send_ipc_message(msg, timeout_ms=350)
    if reply and reply.get("status") == "ok":
        log_debug("Aegis is running. Forwarded request directly and received acceptance.")
        send_native_response({"status": "ok", "message": reply.get("message", "Task accepted by Aegis")})
        sys.exit(0)

    # 3. Slow Path: Aegis is closed or starting up
    log_debug("Aegis is not currently responding. Entering startup and synchronization sequence.")

    # Prevent concurrent duplicate launches using a Windows Named Mutex
    h_mutex = None
    if kernel32:
        try:
            h_mutex = kernel32.CreateMutexW(None, False, "Local\\Aegis_DM_Startup_Lock")
            if h_mutex:
                # Wait up to 15 seconds to acquire startup lock
                kernel32.WaitForSingleObject(h_mutex, 15000)
        except Exception as e:
            log_debug(f"Mutex creation warning: {e}")

    try:
        # Re-check if Aegis became available while waiting on the lock
        reply = send_ipc_message(msg, timeout_ms=300)
        if reply and reply.get("status") == "ok":
            log_debug("Aegis became available while waiting on lock. Request forwarded successfully.")
            send_native_response({"status": "ok", "message": reply.get("message", "Task accepted by Aegis")})
            sys.exit(0)

        # 4. Locate Aegis executable
        aegis_exe = find_aegis_executable()
        if not aegis_exe:
            err_msg = "Aegis Download Manager executable could not be found."
            log_debug(f"ERROR: {err_msg}")
            send_native_response({"status": "error", "error": err_msg})
            sys.exit(0)

        # 5. Launch Aegis cleanly
        started = launch_aegis(aegis_exe)
        if not started:
            err_msg = "Failed to launch Aegis Download Manager process."
            log_debug(f"ERROR: {err_msg}")
            send_native_response({"status": "error", "error": err_msg})
            sys.exit(0)

        # 6. Bounded polling for IPC endpoint readiness and task acceptance
        timeout_seconds = 16.0
        start_wait = time.time()
        final_reply = None

        log_debug(f"Waiting up to {timeout_seconds}s for Aegis IPC server to accept request...")
        while (time.time() - start_wait) < timeout_seconds:
            # Poll named pipe with 400ms timeout
            res = send_ipc_message(msg, timeout_ms=400)
            if res:
                final_reply = res
                break
            time.sleep(0.2)

        # 7. Evaluate confirmation and dispatch response
        if final_reply and final_reply.get("status") == "ok":
            log_debug(f"SUCCESS: Aegis confirmed task acceptance: {final_reply}")
            send_native_response({
                "status": "ok",
                "message": final_reply.get("message", "Task accepted by Aegis Download Manager")
            })
        elif final_reply and final_reply.get("status") == "error":
            err_msg = final_reply.get("message", "Aegis rejected task")
            log_debug(f"ERROR: Aegis returned rejection: {err_msg}")
            send_native_response({"status": "error", "error": err_msg})
        else:
            err_msg = "Aegis Download Manager was started but did not respond to IPC within 16 seconds."
            log_debug(f"TIMEOUT: {err_msg}")
            send_native_response({"status": "error", "error": err_msg})

    finally:
        if kernel32 and h_mutex:
            try:
                kernel32.ReleaseMutex(h_mutex)
                kernel32.CloseHandle(h_mutex)
            except Exception:
                pass

if __name__ == "__main__":
    main()
