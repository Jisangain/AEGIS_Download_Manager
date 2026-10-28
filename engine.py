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
import urllib.request
import urllib.error
import ctypes
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


def is_media_stream_url(url: str) -> bool:
    """Checks if a URL belongs to a streaming or video hosting platform requiring yt-dlp."""
    if not url:
        return False
    u = url.lower().strip()
    stream_patterns = [
        "youtube.com", "youtu.be", "vimeo.com", "dailymotion.com",
        "twitch.tv", "tiktok.com", "facebook.com", "fb.watch",
        "twitter.com", "x.com", "instagram.com", "bilibili.com",
        "soundcloud.com", "bandcamp.com", "rumble.com", "streamable.com"
    ]
    return any(p in u for p in stream_patterns)


def find_tool_binary(tool_name: str, custom_path: str = "") -> Optional[str]:
    """Finds an executable tool (aria2c.exe, ffmpeg.exe, etc.) across candidate paths."""
    if custom_path and os.path.isfile(custom_path):
        return custom_path
        
    exe_name = tool_name if tool_name.endswith(".exe") else f"{tool_name}.exe"
    
    base_dirs = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools"),
        os.path.join(os.path.dirname(os.path.abspath(sys.executable)), "tools"),
        os.path.join(os.path.dirname(os.path.abspath(sys.executable)), "..", "tools"),
        r"E:\reverse\AegisDownloadManager\tools",
        r"E:\reverse\AegisDownloadManager\dist\tools",
        r"E:\reverse\VnA Download Manager\_internal\tools",
        getattr(sys, "_MEIPASS", "")
    ]
    for b in base_dirs:
        if b:
            p = os.path.join(b, exe_name)
            if os.path.isfile(p):
                return os.path.abspath(p)

    found = shutil.which(tool_name) or shutil.which(exe_name)
    if found:
        return os.path.abspath(found)
    return None


def prevent_sleep():
    """Prevents Windows system and network from going to sleep during active downloads."""
    if sys.platform == "win32":
        try:
            # ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_AWAYMODE_REQUIRED
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001 | 0x00000040)
        except Exception:
            pass


def allow_sleep():
    """Restores default Windows power management state when idle."""
    if sys.platform == "win32":
        try:
            # ES_CONTINUOUS
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
        except Exception:
            pass


def parse_size_to_bytes(s: str) -> int:
    """Converts human readable size string (e.g. '1.5GiB', '500MB') to byte count."""
    if not s:
        return 0
    units = {
        "B": 1,
        "K": 1024, "KB": 1024, "KIB": 1024,
        "M": 1024**2, "MB": 1024**2, "MIB": 1024**2,
        "G": 1024**3, "GB": 1024**3, "GIB": 1024**3,
        "T": 1024**4, "TB": 1024**4, "TIB": 1024**4
    }
    m = re.match(r'^([0-9.]+)\s*([A-Za-z]+)?$', s.strip())
    if not m:
        return 0
    val, u = m.groups()
    try:
        mult = units.get(u.upper() if u else "B", 1)
        return int(float(val) * mult)
    except Exception:
        return 0



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
        is_stream = is_media_stream_url(self.url)
        if yt_dlp is not None and (is_stream or not has_direct_ext):
            try:
                deno_bin = find_tool_binary("deno", self.tools.get("deno_path", ""))
                if deno_bin:
                    os.environ["PATH"] = os.path.dirname(deno_bin) + os.pathsep + os.environ.get("PATH", "")

                ydl_opts = {
                    "quiet": True,
                    "no_warnings": True,
                    "extract_flat": False,
                    "skip_download": True,
                    "noplaylist": True
                }
                ffmpeg_bin = find_tool_binary("ffmpeg", self.tools.get("ffmpeg_path", ""))
                if ffmpeg_bin:
                    ydl_opts["ffmpeg_location"] = os.path.dirname(ffmpeg_bin)

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(self.url, download=False)
                    extractor = info.get("extractor", "").lower()
                    
                    # Avoid yt-dlp's generic HTTP fallback if it's just a file
                    if info and (extractor != "generic" or is_stream):
                        title = info.get("title", "video")
                        ext = info.get("ext", "mp4")
                        clean_title = re.sub(r'[\\/*?:"<>|]', "_", title)
                        result["filename"] = f"{clean_title}.{ext}"
                        result["is_media"] = True
                        result["engine"] = "ytdlp"

                        formats_list = []
                        formats_list.append({
                            "id": "bestvideo+bestaudio/best",
                            "label": "Best Available (Auto Highest Quality)",
                            "ext": "mp4"
                        })
                        
                        raw_formats = info.get("formats", [])
                        video_fmts = []
                        for f in raw_formats:
                            fid = str(f.get("format_id", ""))
                            if fid.startswith("sb") or f.get("ext") == "mhtml":
                                continue
                            vc = f.get("vcodec") or "none"
                            if vc == "none":
                                continue
                            h = f.get("height") or 0
                            if h <= 0:
                                continue
                            fps = f.get("fps") or 30
                            f_ext = f.get("ext", "mp4")
                            sz = f.get("filesize") or f.get("filesize_approx") or 0
                            tbr = f.get("tbr") or 0
                            ac = f.get("acodec") or "none"
                            video_fmts.append({
                                "fid": fid,
                                "height": int(h),
                                "fps": int(fps) if fps else 30,
                                "ext": f_ext,
                                "sz": sz,
                                "tbr": tbr,
                                "has_audio": ac != "none"
                            })

                        # Sort: Height desc, FPS desc, known size first, size desc, bitrate desc
                        video_fmts.sort(key=lambda x: (x["height"], x["fps"], 1 if x["sz"] > 0 else 0, x["sz"], x["tbr"]), reverse=True)

                        seen_signatures = set()
                        for vf in video_fmts:
                            h = vf["height"]
                            fps = vf["fps"]
                            f_ext = vf["ext"]
                            fps_key = 60 if fps >= 45 else 30
                            sig = (h, fps_key, f_ext)
                            if sig in seen_signatures:
                                continue
                            seen_signatures.add(sig)

                            if h >= 2160: quality_name = "4K Ultra HD"
                            elif h >= 1440: quality_name = "2K Quad HD"
                            elif h >= 1080: quality_name = "Full HD"
                            elif h >= 720: quality_name = "HD"
                            elif h >= 480: quality_name = "SD"
                            else: quality_name = "Low"

                            fps_str = "60fps" if fps >= 45 else ""
                            res_str = f"{h}p{fps_str}" if fps_str else f"{h}p"
                            parts = [f"{res_str} {quality_name}", f_ext.upper()]
                            if vf["sz"] > 0:
                                mb = vf["sz"] / (1024 * 1024)
                                parts.append(f"~{mb:.1f} MB" if mb < 1024 else f"~{mb/1024:.2f} GB")

                            label = " • ".join(parts)
                            fmt_id = f"{vf['fid']}/best" if vf["has_audio"] else f"{vf['fid']}+bestaudio/best"

                            formats_list.append({
                                "id": fmt_id,
                                "label": label,
                                "ext": f_ext,
                                "height": h
                            })

                        # Audio options
                        formats_list.append({
                            "id": "bestaudio/best",
                            "label": "Audio Only - MP3 (High Quality 192k/320k)",
                            "ext": "mp3"
                        })
                        formats_list.append({
                            "id": "bestaudio[ext=m4a]/bestaudio",
                            "label": "Audio Only - M4A (Original AAC)",
                            "ext": "m4a"
                        })

                        result["formats"] = formats_list
                        self.analysis_complete.emit(result)
                        return
            except Exception:
                if is_stream:
                    # Provide reliable fallback format choices for stream download
                    result["filename"] = "YouTube_Video.mp4"
                    result["is_media"] = True
                    result["engine"] = "ytdlp"
                    result["formats"] = [
                        {"id": "bestvideo+bestaudio/best", "label": "Best Available (4K / 1080p)", "ext": "mp4"},
                        {"id": "bestvideo[height<=1080]+bestaudio/best", "label": "1080p Full HD", "ext": "mp4"},
                        {"id": "bestvideo[height<=720]+bestaudio/best", "label": "720p HD", "ext": "mp4"},
                        {"id": "bestaudio/best", "label": "Audio Only (MP3)", "ext": "mp3"}
                    ]
                    self.analysis_complete.emit(result)
                    return

        # If this is a video stream site, never fallback to raw HTTP probing
        if is_stream:
            result["filename"] = "YouTube_Video.mp4"
            result["is_media"] = True
            result["engine"] = "ytdlp"
            result["formats"] = [
                {"id": "bestvideo+bestaudio/best", "label": "Best Available (4K / 1080p)", "ext": "mp4"},
                {"id": "bestvideo[height<=1080]+bestaudio/best", "label": "1080p Full HD", "ext": "mp4"},
                {"id": "bestvideo[height<=720]+bestaudio/best", "label": "720p HD", "ext": "mp4"},
                {"id": "bestaudio/best", "label": "Audio Only (MP3)", "ext": "mp3"}
            ]
            self.analysis_complete.emit(result)
            return

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
        prevent_sleep()
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
            "--file-allocation=none",
            "--check-certificate=true",
            "--header=User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "--timeout=60",
            "--connect-timeout=30",
            "--max-tries=10",
            "--retry-wait=2",
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
                    try:
                        pct = float(pct_str)
                    except ValueError:
                        pct = 0.0
                    dl_bytes = parse_size_to_bytes(dl_str)
                    tot_bytes = parse_size_to_bytes(tot_str)
                    speed_display = f"{spd_str}/s"
                    eta_display = eta_str if eta_str else "--"
                    self.progress_signal.emit(self.task_id, dl_bytes, tot_bytes, speed_display, eta_display, pct)

            rc = self.process.wait()
            if rc == 0 and os.path.exists(out_file):
                final_size = os.path.getsize(out_file)
                self.progress_signal.emit(self.task_id, final_size, final_size, "0 KB/s", "00:00", 100.0)
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

        deno_bin = find_tool_binary("deno", self.tools.get("deno_path", ""))
        if deno_bin:
            os.environ["PATH"] = os.path.dirname(deno_bin) + os.pathsep + os.environ.get("PATH", "")

        os.makedirs(self.save_dir, exist_ok=True)
        if self.filename and not self.filename.startswith("download"):
            base_name, _ = os.path.splitext(self.filename)
            clean_name = re.sub(r'[\\/*?:"<>|]', "_", base_name)
            base_out = os.path.join(self.save_dir, f"{clean_name}.%(ext)s")
        else:
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
            "format": self.format_id or "bestvideo+bestaudio/best",
            "noplaylist": True
        }

        if self.max_speed_kbs > 0:
            ydl_opts["ratelimit"] = self.max_speed_kbs * 1024

        if ffmpeg_bin:
            ydl_opts["ffmpeg_location"] = os.path.dirname(ffmpeg_bin)
            # If user selected audio-only, extract and transcode to requested format
            if self.format_id == "bestaudio/best" or self.filename.lower().endswith(".mp3"):
                ydl_opts["postprocessors"] = [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }]
            elif self.format_id.startswith("bestaudio[ext=m4a]") or self.filename.lower().endswith(".m4a"):
                ydl_opts["postprocessors"] = [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "m4a",
                    "preferredquality": "192",
                }]
        elif "+" in self.format_id:
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
                final_sz = os.path.getsize(filename)
                self.progress_signal.emit(self.task_id, final_sz, final_sz, "0 KB/s", "00:00", 100.0)
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
    """Pure Python chunked HTTP/HTTPS downloader fallback with rate limiting and auto-resume."""

    def run(self):
        prevent_sleep()
        os.makedirs(self.save_dir, exist_ok=True)
        out_file = os.path.join(self.save_dir, self.filename)

        max_retries = 10
        retry_delay = 2.0
        total = 0

        self.status_signal.emit(self.task_id, "downloading", "")

        for attempt in range(max_retries):
            if self.is_paused:
                self.status_signal.emit(self.task_id, "paused", "")
                return
            if self.is_cancelled:
                self.status_signal.emit(self.task_id, "cancelled", "")
                return

            downloaded = os.path.getsize(out_file) if os.path.exists(out_file) else 0

            req = urllib.request.Request(
                self.url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "*/*",
                    "Connection": "keep-alive"
                }
            )
            if downloaded > 0:
                req.add_header("Range", f"bytes={downloaded}-")

            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    resp_len = resp.headers.get("Content-Length")
                    if resp_len and resp_len.isdigit():
                        seg_len = int(resp_len)
                        total = downloaded + seg_len
                    elif total == 0:
                        total = downloaded

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

                # Finished successfully
                self.progress_signal.emit(self.task_id, downloaded, total, "0 KB/s", "00:00", 100.0)
                self.status_signal.emit(self.task_id, "completed", "")
                self.finished_signal.emit(self.task_id, out_file)
                return

            except urllib.error.HTTPError as he:
                if self.is_paused:
                    self.status_signal.emit(self.task_id, "paused", "")
                    return
                if self.is_cancelled:
                    self.status_signal.emit(self.task_id, "cancelled", "")
                    return
                # Permanent client errors (404, 403, 401, etc.) fail immediately
                if he.code in (400, 401, 403, 404, 405, 410, 416):
                    self.status_signal.emit(self.task_id, "failed", f"HTTP {he.code}: {he.reason}")
                    return
                # Server 5xx errors can be retried
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                else:
                    self.status_signal.emit(self.task_id, "failed", str(he))
                    return

            except Exception as e:
                if self.is_paused:
                    self.status_signal.emit(self.task_id, "paused", "")
                    return
                if self.is_cancelled:
                    self.status_signal.emit(self.task_id, "cancelled", "")
                    return
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                else:
                    self.status_signal.emit(self.task_id, "failed", str(e))
                    return
