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
from ipc_server import send_ipc_message

def read_native_message():
    """Reads a message from the browser using Chrome Native Messaging protocol."""
    raw_length = sys.stdin.buffer.read(4)
    if len(raw_length) < 4:
        return None
    message_length = struct.unpack("@I", raw_length)[0]
    raw_data = sys.stdin.buffer.read(message_length)
    if len(raw_data) < message_length:
        return None
    return json.loads(raw_data.decode("utf-8"))

def send_native_response(payload):
    """Sends a message back to the browser using Chrome Native Messaging protocol."""
    encoded = json.dumps(payload).encode("utf-8")
    sys.stdout.buffer.write(struct.pack("@I", len(encoded)))
    sys.stdout.buffer.write(encoded)
    sys.stdout.buffer.flush()

def ensure_aegis_running():
    """Checks if Aegis is running; launches it if not."""
    exe_candidate = os.path.join(os.path.dirname(__file__), "dist", "Aegis Download Manager.exe")
    if not os.path.exists(exe_candidate):
        exe_candidate = os.path.join(os.path.dirname(__file__), "Aegis Download Manager.exe")
    
    if os.path.exists(exe_candidate):
        try:
            subprocess.Popen([exe_candidate], creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
        except Exception:
            pass

def main():
    msg = read_native_message()
    if not msg:
        sys.exit(0)

    # Try sending to running Aegis via named pipe
    reply = send_ipc_message(msg, timeout_ms=2000)
    if not reply:
        # Launch Aegis and try again
        ensure_aegis_running()
        reply = send_ipc_message(msg, timeout_ms=5000)

    if reply:
        send_native_response(reply)
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
            send_native_response({"status": "queued", "message": "Saved to Aegis launch queue"})
        except Exception as e:
            send_native_response({"status": "error", "message": f"Could not reach Aegis: {str(e)}"})

if __name__ == "__main__":
    main()
