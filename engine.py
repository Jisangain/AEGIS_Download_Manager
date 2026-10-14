"""
Aegis Download Manager - Engine Layer
Orchestrates aria2c, yt-dlp, and native HTTP downloads with zero license dependencies.
"""

import os
import sys
import re
import time
import shutil
import subprocess
import urllib.parse
# urllib.request
from typing import Dict, Any, List, Optional, Tuple
from PyQt6.QtCore import QObject, QThread, pyqtSignal

# Import or dynamically load yt_dlp
try:
    import yt_dlp
except ImportError:
    possible_zips = [
        os.path.join(os.path.dirname(__file__), "tools", "yt-dlp-module.zip"),
        os.path.join("E:\\reverse\\VnA Download Manager\\_internal\\tools", "yt-dlp-module.zip")
    ]
    yt_dlp = None
    for pz in possible_zips:
        if os.path.exists(pz):
            sys.path.insert(0, pz)
            try:
                import yt_dlp
                break
            except ImportError:
                pass


def find_tool_binary(tool_name: str, custom_path: str = "") -> Optional[str]:
    """Finds an executable tool (aria2c.exe, ffmpeg.exe, etc.) across candidate paths."""
    if custom_path and os.path.isfile(custom_path):
        return custom_path
        
    exe_name = tool_name if tool_name.endswith(".exe") else f"{tool_name}.exe"
    
    candidates = [
        os.path.join(os.path.dirname(__file__), "tools", exe_name),
        os.path.join("E:\\reverse\\VnA Download Manager\\_internal\\tools", exe_name),
        shutil.which(tool_name) or "",
        shutil.which(exe_name) or ""
    ]
    for c in candidates:
        if c and os.path.isfile(c):
            return os.path.abspath(c)
    return None


class UrlAnalyzerThread(QThread):
    """Probes a URL to determine filename, size, and available media stream formats."""
    analysis_complete = pyqtSignal(dict)
    analysis_failed = pyqtSignal(str)

    def __init__(self, url: str, custom_tools: Optional[Dict[str, str]] = None):
        super().__init__()
        self.url = url.strip()
        self.tools = custom_tools or {}

    def run(self):
        result = {
            "url": self.url,
            "filename": "download",
            "filesize": 0,
            "is_media": False,
            "formats": [],
            "engine": "direct"
        }
        
        parsed_url = urllib.parse.urlparse(self.url)
        path_lower = parsed_url.path.lower()
        direct_exts = {
            ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".iso",
            ".exe", ".msi", ".apk", ".bin", ".dmg",
            ".pdf", ".docx", ".doc", ".xlsx", ".txt", ".md",
            ".png", ".jpg", ".jpeg", ".gif", ".webp"
        }
        has_direct_ext = any(path_lower.endswith(ext) for ext in direct_exts)

        # 1. Probe with yt-dlp only if not an obvious static direct file extension
        if yt_dlp is not None and not has_direct_ext:
            try:
                ydl_opts = {
                    "quiet": True,
                    "no_warnings": True,
                    "extract_flat": False,
                    "skip_download": True,
                    "extractor_args": {"youtube": {"player_client": ["android", "ios", "web"]}}
                }
                ffmpeg_bin = find_tool_binary("ffmpeg", self.tools.get("ffmpeg_path", ""))
                if ffmpeg_bin:
                    ydl_opts["ffmpeg_location"] = os.path.dirname(ffmpeg_bin)

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(self.url, download=False)
                    extractor = info.get("extractor", "").lower()
                    
                    # Avoid yt-dlp's generic HTTP fallback if it's just a file
                    if info and extractor != "generic":
                        title = info.get("title", "video")
                        ext = info.get("ext", "mp4")
                        clean_title = re.sub(r'[\\/*?:"<>|]', "_", title)
                        result["filename"] = f"{clean_title}.{ext}"
                        result["is_media"] = True
                        result["engine"] = "ytdlp"

                        formats_list = []
                        formats_list.append({
                            "id": "bestvideo+bestaudio/best",
                            "label": "Best Quality (Auto Video + Audio)",
                            "ext": "mp4"
                        })
                        
                        seen_res = set()
                        raw_formats = info.get("formats", [])
                        for f in raw_formats:
                            height = f.get("height")
                            f_id = f.get("format_id")
                            vcodec = f.get("vcodec", "none")
                            if height and height not in seen_res and vcodec != "none":
                                seen_res.add(height)
                                formats_list.append({
                                    "id": f"bestvideo[height<={height}]+bestaudio/best[height<={height}]",
                                    "label": f"{height}p Video ({f.get('ext', 'mp4')})",
                                    "ext": f.get("ext", "mp4")
                                })

                        formats_list.append({
                            "id": "bestaudio/best",
                            "label": "Audio Only (MP3 / Best Audio)",
                            "ext": "mp3"
                        })

                        result["formats"] = formats_list
                        self.analysis_complete.emit(result)
                        return
            except Exception:
                pass

        # 2. Standard HTTP/HTTPS Direct Link Probe
        try:
            # urllib.request
            req = urllib.request.Request(self.url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            req.get_method = lambda: "HEAD"
            try:
                with urllib.request.urlopen(req, timeout=10) as resp:
                    headers = resp.headers
            except Exception:
                req.get_method = lambda: "GET"
                req.add_header("Range", "bytes=0-0")
                with urllib.request.urlopen(req, timeout=10) as resp:
                    headers = resp.headers

            content_disp = headers.get("Content-Disposition", "")
            fname = ""
            if "filename=" in content_disp:
                match = re.search(r'filename\*?=(?:UTF-8\'\')?["\']?([^"\';]+)["\']?', content_disp)
                if match:
                    fname = urllib.parse.unquote(match.group(1))

            if not fname:
                fname = os.path.basename(parsed_url.path) or "download.bin"

            result["filename"] = re.sub(r'[\\/*?:"<>|]', "_", fname)

            content_length = headers.get("Content-Length")
            if content_length and content_length.isdigit():
                result["filesize"] = int(content_length)

            aria2_bin = find_tool_binary("aria2c", self.tools.get("aria2_path", ""))
            result["engine"] = "aria2" if aria2_bin else "direct"
            
            self.analysis_complete.emit(result)
        except Exception as e:
            result["filename"] = os.path.basename(parsed_url.path) or "download.bin"
            result["engine"] = "direct"
            self.analysis_complete.emit(result)


class BaseDownloadWorker(QThread):
    progress_signal = pyqtSignal(int, int, int, str, str, float)
    status_signal = pyqtSignal(int, str, str)
    finished_signal = pyqtSignal(int, str)

    def __init__(self, task_id: int, url: str, filename: str, save_dir: str, 
                 connections: int = 16, format_id: str = "", tools_config: Optional[Dict[str, str]] = None,
                 max_speed_kbs: int = 0):
        super().__init__()
        self.task_id = task_id
        self.url = url
        self.filename = filename
        self.save_dir = save_dir
        self.connections = connections
        self.format_id = format_id
        self.tools = tools_config or {}
        self.max_speed_kbs = max_speed_kbs
        self.is_paused = False
        self.is_cancelled = False
        self.process: Optional[subprocess.Popen] = None

    def pause(self):
        self.is_paused = True
        if self.process:
            try:
                self.process.terminate()
            except Exception:
                pass

    def cancel(self):
        self.is_cancelled = True
        if self.process:
            try:
                self.process.kill()
            except Exception:
                pass


class Aria2Worker(BaseDownloadWorker):
    """Executes multi-segmented downloads with aria2c.exe."""
    
    def run(self):
        aria2_bin = find_tool_binary("aria2c", self.tools.get("aria2_path", ""))
        if not aria2_bin:
            self.status_signal.emit(self.task_id, "failed", "aria2c executable not found")
            return

        os.makedirs(self.save_dir, exist_ok=True)
        out_file = os.path.join(self.save_dir, self.filename)

        cmd = [
            aria2_bin,
            "-c",
            f"-s{self.connections}",
            f"-x{self.connections}",
            "-k1M",
            "--summary-interval=1",
            "--show-console-readout=false",
            f"--dir={self.save_dir}",
            f"--out={self.filename}"
        ]
        if self.max_speed_kbs > 0:
            cmd.append(f"--max-download-limit={self.max_speed_kbs}K")
        cmd.append(self.url)

        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )

            self.status_signal.emit(self.task_id, "downloading", "")
            downloaded = 0
            total = 0

            progress_regex = re.compile(
                r'\[#\w+\s+([0-9.]+[A-Za-z]+)/([0-9.]+[A-Za-z]+)\(([0-9.]+)%\)\s+.*?DL:([0-9.]+[A-Za-z]+)(?:\s+ETA:([0-9A-Za-z]+))?\]'
            )

            while True:
                if self.is_paused:
                    self.status_signal.emit(self.task_id, "paused", "")
                    return
                if self.is_cancelled:
                    self.status_signal.emit(self.task_id, "cancelled", "")
                    return

                line = self.process.stdout.readline()
                if not line:
                    if self.process.poll() is not None:
                        break
                    continue

                m = progress_regex.search(line)
                if m:
                    dl_str, tot_str, pct_str, spd_str, eta_str = m.groups()
                    pct = float(pct_str)
                    speed_display = f"{spd_str}/s"
                    eta_display = eta_str if eta_str else "--"
                    self.progress_signal.emit(self.task_id, 0, 0, speed_display, eta_display, pct)

            rc = self.process.wait()
            if rc == 0 and os.path.exists(out_file):
                self.progress_signal.emit(self.task_id, 0, 0, "0 KB/s", "00:00", 100.0)
                self.status_signal.emit(self.task_id, "completed", "")
                self.finished_signal.emit(self.task_id, out_file)
            elif not self.is_paused and not self.is_cancelled:
                self.status_signal.emit(self.task_id, "failed", f"aria2c exited with code {rc}")
        except Exception as e:
            if not self.is_paused and not self.is_cancelled:
                self.status_signal.emit(self.task_id, "failed", str(e))


class YtDlpWorker(BaseDownloadWorker):
    """Executes media stream extraction and downloading via yt-dlp."""

    def run(self):
        if yt_dlp is None:
            self.status_signal.emit(self.task_id, "failed", "yt-dlp is not available")
            return

        os.makedirs(self.save_dir, exist_ok=True)
        base_out = os.path.join(self.save_dir, "%(title)s.%(ext)s")

        ffmpeg_bin = find_tool_binary("ffmpeg", self.tools.get("ffmpeg_path", ""))

        def progress_hook(d):
            if self.is_cancelled or self.is_paused:
                raise InterruptedError("Download interrupted by user")

            status = d.get("status")
            if status == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                downloaded = d.get("downloaded_bytes", 0)
                pct = (downloaded / total * 100.0) if total > 0 else 0.0
                speed = d.get("speed") or 0
                speed_str = f"{speed / (1024*1024):.2f} MB/s" if speed >= 1048576 else f"{speed / 1024:.2f} KB/s"
                eta = d.get("eta")
                eta_str = f"{eta}s" if eta is not None else "--"

                self.progress_signal.emit(self.task_id, downloaded, total, speed_str, eta_str, pct)
            elif status == "finished":
                self.progress_signal.emit(self.task_id, 0, 0, "Processing...", "--", 99.0)

        ydl_opts = {
            "outtmpl": base_out,
            "progress_hooks": [progress_hook],
            "quiet": True,
            "no_warnings": True,
            "extractor_args": {"youtube": {"player_client": ["android", "ios", "web"]}},
            "format": self.format_id or "bestvideo+bestaudio/best"
        }

        if self.max_speed_kbs > 0:
            ydl_opts["ratelimit"] = self.max_speed_kbs * 1024

        if ffmpeg_bin:
            ydl_opts["ffmpeg_location"] = os.path.dirname(ffmpeg_bin)
            # If user selected audio-only, extract and transcode to MP3
            if self.format_id == "bestaudio/best" or self.filename.lower().endswith(".mp3"):
                ydl_opts["postprocessors"] = [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }]
        elif self.format_id == "bestvideo+bestaudio/best":
            # If FFmpeg is missing, prefer single container format to avoid unmerged streams
            ydl_opts["format"] = "best[ext=mp4]/best"

        try:
            self.status_signal.emit(self.task_id, "downloading", "")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.url, download=True)
                filename = ydl.prepare_filename(info)
                # If audio was converted to mp3, update filename extension
                if self.format_id == "bestaudio/best" or self.filename.lower().endswith(".mp3"):
                    base_root, _ = os.path.splitext(filename)
                    mp3_path = f"{base_root}.mp3"
                    if os.path.exists(mp3_path):
                        filename = mp3_path
                
            if os.path.exists(filename):
                self.progress_signal.emit(self.task_id, 0, 0, "0 KB/s", "00:00", 100.0)
                self.status_signal.emit(self.task_id, "completed", "")
                self.finished_signal.emit(self.task_id, filename)
            else:
                self.status_signal.emit(self.task_id, "completed", "")
        except InterruptedError:
            if self.is_paused:
                self.status_signal.emit(self.task_id, "paused", "")
            else:
                self.status_signal.emit(self.task_id, "cancelled", "")
        except Exception as e:
            self.status_signal.emit(self.task_id, "failed", str(e))


class DirectHttpWorker(BaseDownloadWorker):
    """Pure Python chunked HTTP/HTTPS downloader fallback with rate limiting."""

    def run(self):
        # urllib.request
        os.makedirs(self.save_dir, exist_ok=True)
        out_file = os.path.join(self.save_dir, self.filename)

        downloaded = 0
        if os.path.exists(out_file):
            downloaded = os.path.getsize(out_file)

        req = urllib.request.Request(self.url, headers={"User-Agent": "Mozilla/5.0"})
        if downloaded > 0:
            req.add_header("Range", f"bytes={downloaded}-")

        try:
            self.status_signal.emit(self.task_id, "downloading", "")
            with urllib.request.urlopen(req, timeout=15) as resp:
                total = int(resp.headers.get("Content-Length", 0)) + downloaded
                mode = "ab" if downloaded > 0 else "wb"
                
                start_time = time.time()
                last_update = start_time
                bytes_since_update = 0

                with open(out_file, mode) as f:
                    while True:
                        if self.is_paused:
                            self.status_signal.emit(self.task_id, "paused", "")
                            return
                        if self.is_cancelled:
                            self.status_signal.emit(self.task_id, "cancelled", "")
                            return

                        chunk_start = time.time()
                        chunk = resp.read(64 * 1024)
                        if not chunk:
                            break

                        f.write(chunk)
                        chunk_len = len(chunk)
                        downloaded += chunk_len
                        bytes_since_update += chunk_len

                        # Speed limiter throttle for direct HTTP
                        if self.max_speed_kbs > 0:
                            expected_time = chunk_len / (self.max_speed_kbs * 1024)
                            chunk_elapsed = time.time() - chunk_start
                            if expected_time > chunk_elapsed:
                                sleep_sec = min(1.0, expected_time - chunk_elapsed)
                                time.sleep(sleep_sec)

                        now = time.time()
                        if now - last_update >= 0.5:
                            duration = now - last_update
                            speed = bytes_since_update / duration
                            speed_str = f"{speed / (1024*1024):.2f} MB/s" if speed >= 1048576 else f"{speed / 1024:.2f} KB/s"
                            remaining = (total - downloaded) if total > downloaded else 0
                            eta_sec = int(remaining / speed) if speed > 0 else 0
                            eta_str = f"{eta_sec // 60:02d}:{eta_sec % 60:02d}"
                            pct = (downloaded / total * 100.0) if total > 0 else 0.0

                            self.progress_signal.emit(self.task_id, downloaded, total, speed_str, eta_str, pct)
                            last_update = now
                            bytes_since_update = 0

            self.progress_signal.emit(self.task_id, downloaded, total, "0 KB/s", "00:00", 100.0)
            self.status_signal.emit(self.task_id, "completed", "")
            self.finished_signal.emit(self.task_id, out_file)
        except Exception as e:
            if not self.is_paused and not self.is_cancelled:
                self.status_signal.emit(self.task_id, "failed", str(e))
