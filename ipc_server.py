"""Cross-platform local IPC server used by Aegis browser integration."""

import ctypes
import json
import os
import socket
import stat
import sys
import time

from PyQt6.QtCore import QThread, pyqtSignal

if sys.platform == "win32":
    from ctypes import wintypes
else:
    wintypes = None

from ipc_transport import (
    GENERIC_WRITE,
    INVALID_HANDLE_VALUE,
    OPEN_EXISTING,
    PIPE_ACCESS_DUPLEX,
    PIPE_NAME,
    PIPE_TYPE_BYTE,
    PIPE_WAIT,
    kernel32,
    send_ipc_message,
    unix_socket_path,
)

MAX_MESSAGE_BYTES = 10 * 1024 * 1024


class AegisIpcServer(QThread):
    """Accept requests over a Windows named pipe or a POSIX domain socket."""

    message_received = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.running = True
        self._current_handle = None
        self._unix_server = None
        self._owns_unix_socket = False

    def run(self):
        if sys.platform == "win32":
            self._run_windows()
        elif hasattr(socket, "AF_UNIX"):
            self._run_unix()

    def _run_windows(self):
        while self.running:
            handle = kernel32.CreateNamedPipeW(
                PIPE_NAME,
                PIPE_ACCESS_DUPLEX,
                PIPE_TYPE_BYTE | PIPE_WAIT,
                255,
                65536,
                65536,
                1000,
                None,
            )
            if handle == INVALID_HANDLE_VALUE or handle == 0:
                time.sleep(0.5)
                continue

            self._current_handle = handle
            connected = kernel32.ConnectNamedPipe(handle, None)
            if connected or kernel32.GetLastError() == 535:
                buf = ctypes.create_string_buffer(65536)
                bytes_read = wintypes.DWORD(0)
                success = kernel32.ReadFile(handle, buf, 65535, ctypes.byref(bytes_read), None)
                if success and bytes_read.value > 0:
                    self._handle_message(
                        buf.raw[:bytes_read.value], lambda data: self._write_windows(handle, data)
                    )
                kernel32.FlushFileBuffers(handle)
                kernel32.DisconnectNamedPipe(handle)

            kernel32.CloseHandle(handle)
            self._current_handle = None

    @staticmethod
    def _write_windows(handle, data: bytes):
        written = wintypes.DWORD(0)
        kernel32.WriteFile(handle, data, len(data), ctypes.byref(written), None)

    def _run_unix(self):
        path = unix_socket_path()
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._unix_server = server
        try:
            if os.path.lexists(path):
                try:
                    existing = os.lstat(path)
                except FileNotFoundError:
                    existing = None
                if existing is not None and (
                    not stat.S_ISSOCK(existing.st_mode)
                    or (hasattr(os, "getuid") and existing.st_uid != os.getuid())
                ):
                    return
                probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                try:
                    probe.settimeout(0.25)
                    probe.connect(path)
                    return
                except OSError:
                    try:
                        current = os.lstat(path)
                        if existing and (current.st_dev, current.st_ino) == (existing.st_dev, existing.st_ino):
                            os.unlink(path)
                    except FileNotFoundError:
                        pass
                finally:
                    probe.close()

            server.bind(path)
            self._owns_unix_socket = True
            os.chmod(path, 0o600)
            server.listen(8)
            server.settimeout(0.5)
            while self.running:
                try:
                    client, _ = server.accept()
                except socket.timeout:
                    continue
                except OSError:
                    if self.running:
                        time.sleep(0.1)
                    continue
                with client:
                    self._handle_unix_client(client)
        except OSError:
            return
        finally:
            try:
                server.close()
            except OSError:
                pass
            self._unix_server = None
            if self._owns_unix_socket:
                try:
                    os.unlink(path)
                except FileNotFoundError:
                    pass
                self._owns_unix_socket = False

    def _handle_unix_client(self, client):
        client.settimeout(2.0)
        raw = bytearray()
        try:
            while len(raw) <= MAX_MESSAGE_BYTES:
                part = client.recv(min(65536, MAX_MESSAGE_BYTES + 1 - len(raw)))
                if not part:
                    break
                raw.extend(part)
            if len(raw) > MAX_MESSAGE_BYTES:
                client.sendall(json.dumps({
                    "status": "error", "message": "IPC message is too large"
                }).encode("utf-8"))
                return
            self._handle_message(bytes(raw), client.sendall)
        except (OSError, ValueError):
            pass

    def _handle_message(self, raw_data: bytes, send_reply):
        try:
            message = json.loads(raw_data.decode("utf-8"))
            if not isinstance(message, dict):
                raise ValueError("IPC payload must be a JSON object")
            self.message_received.emit(message)
            reply = {"status": "ok", "message": "Task received by Aegis"}
        except Exception as exc:
            reply = {"status": "error", "message": str(exc)}
        send_reply(json.dumps(reply).encode("utf-8"))

    def stop(self):
        self.running = False
        if kernel32 and self._current_handle:
            try:
                client = kernel32.CreateFileW(
                    PIPE_NAME, GENERIC_WRITE, 0, None, OPEN_EXISTING, 0, None
                )
                if client != INVALID_HANDLE_VALUE and client != 0:
                    kernel32.CloseHandle(client)
            except Exception:
                pass
        if self._unix_server:
            try:
                self._unix_server.close()
            except OSError:
                pass
