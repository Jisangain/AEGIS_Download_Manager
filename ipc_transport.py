"""Cross-platform local IPC client used by Aegis and its browser host."""

import ctypes
import json
import os
import socket
import stat
import sys
import tempfile
import time
from typing import Any, Dict, Optional

if sys.platform == "win32":
    from ctypes import wintypes
else:
    wintypes = None

PIPE_NAME = r"\\.\pipe\Aegis_Download_Manager_Pipe"
MAX_MESSAGE_BYTES = 10 * 1024 * 1024

PIPE_ACCESS_DUPLEX = 0x00000003
PIPE_TYPE_BYTE = 0x00000000
PIPE_WAIT = 0x00000000
INVALID_HANDLE_VALUE = -1
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
OPEN_EXISTING = 3

kernel32 = ctypes.windll.kernel32 if sys.platform == "win32" else None


def unix_socket_path() -> str:
    """Use a per-user runtime socket, with a private cache fallback."""
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
    if runtime_dir and os.path.isdir(runtime_dir):
        return os.path.join(runtime_dir, "aegis-download-manager.sock")

    if hasattr(os, "getuid"):
        base = os.path.join(tempfile.gettempdir(), f"aegis-download-manager-{os.getuid()}")
    else:
        base = os.path.join(os.path.expanduser("~"), ".cache", "aegis-download-manager")
    os.makedirs(base, mode=0o700, exist_ok=True)
    try:
        os.chmod(base, 0o700)
    except OSError:
        pass
    return os.path.join(base, "ipc.sock")


def _send_windows_message(payload: Dict[str, Any], timeout_ms: int) -> Optional[Dict[str, Any]]:
    start_wait = time.monotonic()
    while (time.monotonic() - start_wait) * 1000 < timeout_ms:
        client = kernel32.CreateFileW(
            PIPE_NAME, GENERIC_READ | GENERIC_WRITE, 0, None, OPEN_EXISTING, 0, None
        )
        if client != INVALID_HANDLE_VALUE and client != 0:
            break
        time.sleep(0.1)
    else:
        return None

    try:
        raw_out = json.dumps(payload).encode("utf-8")
        if len(raw_out) > MAX_MESSAGE_BYTES:
            return None
        bytes_written = wintypes.DWORD(0)
        if not kernel32.WriteFile(client, raw_out, len(raw_out), ctypes.byref(bytes_written), None):
            return None
        buf = ctypes.create_string_buffer(MAX_MESSAGE_BYTES)
        bytes_read = wintypes.DWORD(0)
        success = kernel32.ReadFile(
            client, buf, MAX_MESSAGE_BYTES - 1, ctypes.byref(bytes_read), None
        )
        if success and bytes_read.value > 0:
            return json.loads(buf.raw[:bytes_read.value].decode("utf-8"))
        return None
    finally:
        kernel32.CloseHandle(client)


def _send_unix_message(payload: Dict[str, Any], timeout_ms: int) -> Optional[Dict[str, Any]]:
    deadline = time.monotonic() + max(timeout_ms, 0) / 1000
    message = json.dumps(payload).encode("utf-8")
    if len(message) > MAX_MESSAGE_BYTES:
        return None

    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return None
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.settimeout(remaining)
        try:
            client.connect(unix_socket_path())
            client.sendall(message)
            client.shutdown(socket.SHUT_WR)
            chunks = bytearray()
            while len(chunks) <= MAX_MESSAGE_BYTES:
                part = client.recv(min(65536, MAX_MESSAGE_BYTES + 1 - len(chunks)))
                if not part:
                    break
                chunks.extend(part)
            if len(chunks) > MAX_MESSAGE_BYTES:
                return None
            return json.loads(chunks.decode("utf-8")) if chunks else None
        except (OSError, ValueError, json.JSONDecodeError):
            time.sleep(min(0.1, max(0, remaining)))
        finally:
            client.close()


def send_ipc_message(
    payload: Dict[str, Any], timeout_ms: int = 3000
) -> Optional[Dict[str, Any]]:
    """Send one JSON request to the running desktop app."""
    if sys.platform == "win32":
        return _send_windows_message(payload, timeout_ms)
    if hasattr(socket, "AF_UNIX"):
        return _send_unix_message(payload, timeout_ms)
    return None

