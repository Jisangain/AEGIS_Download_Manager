"""
Aegis Download Manager - Local IPC Server & Client
Clean, independent Windows Named Pipe communication for browser native messaging.
No dependency on external libraries or proprietary pipes.
"""

import os
import sys
import json
import time
import ctypes
from ctypes import wintypes
from typing import Optional, Dict, Any, Callable
from PyQt6.QtCore import QThread, pyqtSignal

PIPE_NAME = r"\\.\pipe\Aegis_Download_Manager_Pipe"

PIPE_ACCESS_DUPLEX = 0x00000003
PIPE_TYPE_BYTE = 0x00000000
PIPE_WAIT = 0x00000000
INVALID_HANDLE_VALUE = -1
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
OPEN_EXISTING = 3

kernel32 = ctypes.windll.kernel32 if sys.platform == "win32" else None

class AegisIpcServer(QThread):
    r"""Listens on \\.\pipe\Aegis_Download_Manager_Pipe for browser download requests."""
    message_received = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.running = True
        self._current_handle = None

    def run(self):
        if not kernel32:
            return

        while self.running:
            handle = kernel32.CreateNamedPipeW(
                PIPE_NAME,
                PIPE_ACCESS_DUPLEX,
                PIPE_TYPE_BYTE | PIPE_WAIT,
                255,   # Max instances
                65536, # Out buffer size
                65536, # In buffer size
                1000,  # Default timeout (ms)
                None
            )

            if handle == INVALID_HANDLE_VALUE or handle == 0:
                time.sleep(0.5)
                continue

            self._current_handle = handle
            connected = kernel32.ConnectNamedPipe(handle, None)
            # 0 and ERROR_PIPE_CONNECTED (535) means client already connected
            last_err = kernel32.GetLastError()
            if connected or last_err == 535:
                buf = ctypes.create_string_buffer(65536)
                bytes_read = wintypes.DWORD(0)
                success = kernel32.ReadFile(
                    handle,
                    buf,
                    65535,
                    ctypes.byref(bytes_read),
                    None
                )
                if success and bytes_read.value > 0:
                    raw_data = buf.raw[:bytes_read.value]
                    try:
                        msg = json.loads(raw_data.decode("utf-8"))
                        self.message_received.emit(msg)
                        reply = json.dumps({"status": "ok", "message": "Task received by Aegis"}).encode("utf-8")
                    except Exception as e:
                        reply = json.dumps({"status": "error", "message": str(e)}).encode("utf-8")

                    bytes_written = wintypes.DWORD(0)
                    kernel32.WriteFile(
                        handle,
                        reply,
                        len(reply),
                        ctypes.byref(bytes_written),
                        None
                    )

                kernel32.FlushFileBuffers(handle)
                kernel32.DisconnectNamedPipe(handle)

            kernel32.CloseHandle(handle)
            self._current_handle = None

    def stop(self):
        self.running = False
        # Unblock listening handle if any
        if kernel32 and self._current_handle:
            try:
                # Connect a dummy client to unblock ConnectNamedPipe
                client = kernel32.CreateFileW(
                    PIPE_NAME,
                    GENERIC_WRITE,
                    0, None,
                    OPEN_EXISTING,
                    0, None
                )
                if client != INVALID_HANDLE_VALUE and client != 0:
                    kernel32.CloseHandle(client)
            except Exception:
                pass


def send_ipc_message(payload: Dict[str, Any], timeout_ms: int = 3000) -> Optional[Dict[str, Any]]:
    """Sends a JSON message to Aegis via the local named pipe."""
    if not kernel32:
        return None

    # Wait for pipe to be available
    start_wait = time.time()
    while (time.time() - start_wait) * 1000 < timeout_ms:
        client = kernel32.CreateFileW(
            PIPE_NAME,
            GENERIC_READ | GENERIC_WRITE,
            0, None,
            OPEN_EXISTING,
            0, None
        )
        if client != INVALID_HANDLE_VALUE and client != 0:
            break
        time.sleep(0.1)
    else:
        return None

    try:
        raw_out = json.dumps(payload).encode("utf-8")
        bytes_written = wintypes.DWORD(0)
        kernel32.WriteFile(
            client,
            raw_out,
            len(raw_out),
            ctypes.byref(bytes_written),
            None
        )

        buf = ctypes.create_string_buffer(65536)
        bytes_read = wintypes.DWORD(0)
        success = kernel32.ReadFile(
            client,
            buf,
            65535,
            ctypes.byref(bytes_read),
            None
        )
        if success and bytes_read.value > 0:
            raw_in = buf.raw[:bytes_read.value]
            return json.loads(raw_in.decode("utf-8"))
        return None
    finally:
        kernel32.CloseHandle(client)
