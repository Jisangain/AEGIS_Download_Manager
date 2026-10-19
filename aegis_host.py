"""
Aegis Download Manager - Native Messaging Host
Bridges Chrome and Edge browser extensions to Aegis via local Named Pipe IPC.
Zero dependencies, pure standard library.
"""

import sys
import os
import struct
import json
import subprocess
from datetime import datetime
from ipc_server import send_ipc_message

if sys.platform == "win32":
    import msvcrt
    try:
        msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
        msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
    except Exception:
        pass

def log_debug(msg: str):
    try:
        app_data = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "AegisDownloadManager")
        os.makedirs(app_data, exist_ok=True)
        with open(os.path.join(app_data, "aegis_host.log"), "a", encoding="utf-8") as f:
            f.write(f"{datetime.now().isoformat()} - {msg}\n")
    except Exception:
        pass

def read_native_message():
    """Reads a message from the browser using Chrome Native Messaging protocol."""
    try:
        raw_length = sys.stdin.buffer.read(4)
        if len(raw_length) < 4:
            log_debug("Native message raw_length < 4")
            return None
        message_length = struct.unpack("@I", raw_length)[0]
        raw_data = sys.stdin.buffer.read(message_length)
        if len(raw_data) < message_length:
            log_debug(f"Truncated message: read {len(raw_data)} of {message_length}")
            return None
        parsed = json.loads(raw_data.decode("utf-8"))
        log_debug(f"Received native message: {parsed}")
        return parsed
    except Exception as e:
        log_debug(f"Exception reading native message: {e}")
        return None

def send_native_response(payload):
    """Sends a message back to the browser using Chrome Native Messaging protocol."""
    try:
        encoded = json.dumps(payload).encode("utf-8")
        sys.stdout.buffer.write(struct.pack("@I", len(encoded)))
        sys.stdout.buffer.write(encoded)
        sys.stdout.buffer.flush()
    except Exception as e:
        log_debug(f"Failed to send native response (pipe closed): {e}")

def ensure_aegis_running(url: str = "", filename: str = "", format_id: str = ""):
    """Checks if Aegis is running; launches it with task parameters if not."""
    if getattr(sys, "frozen", False):
        cur_dir = os.path.dirname(os.path.abspath(sys.executable))
    else:
        cur_dir = os.path.dirname(os.path.abspath(__file__))

    candidates = [
        os.path.join(cur_dir, "Aegis Download Manager.exe"),
        os.path.join(cur_dir, "dist", "Aegis Download Manager.exe"),
        os.path.join(cur_dir, "..", "Aegis Download Manager.exe"),
        os.path.join(cur_dir, "..", "dist", "Aegis Download Manager.exe"),
        r"E:\reverse\AegisDownloadManager\Aegis Download Manager.exe",
        r"E:\reverse\AegisDownloadManager\dist\Aegis Download Manager.exe",
    ]
    for exe in candidates:
        abs_exe = os.path.abspath(exe)
        if os.path.exists(abs_exe):
            try:
                cmd = [abs_exe]
                if url:
                    cmd.extend(["/d", url])
                if filename:
                    cmd.extend(["/f", filename])
                if format_id:
                    cmd.extend(["/format", format_id])

                if sys.platform == "win32":
                    try:
                        args_str = " ".join(f'"{a}"' if " " in a else a for a in cmd[1:])
                        os.startfile(abs_exe, arguments=args_str)
                        log_debug(f"Successfully launched Aegis via os.startfile from {abs_exe} with args: {args_str}")
                        return True
                    except Exception as ex_start:
                        log_debug(f"os.startfile failed: {ex_start}, falling back to Popen")

                # Fallback: DETACHED_PROCESS (0x00000008) | CREATE_NEW_PROCESS_GROUP (0x00000200)
                flags = 0x00000208 if sys.platform == "win32" else 0
                subprocess.Popen(cmd, creationflags=flags)
                log_debug(f"Successfully launched Aegis from {abs_exe} with args: {cmd[1:]}")
                return True
            except Exception as e:
                log_debug(f"Failed to launch {abs_exe}: {e}")
    log_debug("Could not find any Aegis Download Manager executable")
    return False

def main():
    log_debug("aegis_host invoked")
    msg = read_native_message()
    if not msg:
        log_debug("No native message, exiting")
        sys.exit(0)

    # Try sending to running Aegis via named pipe
    reply = send_ipc_message(msg, timeout_ms=1500)
    log_debug(f"Initial IPC reply: {reply}")
    if not reply:
        # Launch Aegis and try again
        log_debug("Aegis not responding, attempting to launch")
        ensure_aegis_running(
            url=msg.get("url", ""),
            filename=msg.get("filename", ""),
            format_id=msg.get("format_id", "")
        )
        reply = send_ipc_message(msg, timeout_ms=4000)
        log_debug(f"Post-launch IPC reply: {reply}")

    if reply:
        send_native_response(reply)
        log_debug("Sent success response to browser")
    else:
        # Fallback: Save to browser queue in AppData so Aegis picks it up on next start
        app_data = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "AegisDownloadManager")
        os.makedirs(app_data, exist_ok=True)
        queue_file = os.path.join(app_data, "browser_queue.json")
        try:
            existing = []
            if os.path.exists(queue_file):
                with open(queue_file, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            existing.append(msg)
            with open(queue_file, "w", encoding="utf-8") as f:
                json.dump(existing, f, indent=2)
            log_debug("Enqueued message to browser_queue.json")
            send_native_response({"status": "queued", "message": "Saved to Aegis launch queue"})
        except Exception as e:
            log_debug(f"Failed writing browser queue: {e}")
            send_native_response({"status": "error", "message": f"Could not reach Aegis: {str(e)}"})

if __name__ == "__main__":
    main()
