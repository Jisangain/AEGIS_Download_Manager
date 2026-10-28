"""
Aegis Download Manager - Automation & File Management Layer
Handles:
1. Smart folder routing & category mapping
2. File integrity hashing (MD5, SHA1, SHA256)
3. Windows Defender antivirus scanning
4. Safe archive extraction (.zip, .tar, .gz, .bz2, .xz)
5. Recursive Site Grabber & HTML link crawler
"""

import os
import re
import sys
import shutil
import hashlib
import zipfile
import tarfile
import subprocess
import urllib.request
import urllib.parse
from typing import Dict, Any, List, Optional, Callable
from bs4 import BeautifulSoup


# Category definitions with canonical file extensions
CATEGORY_MAP = {
    "Video": [".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".3gp", ".ts"],
    "Audio": [".mp3", ".wav", ".aac", ".flac", ".ogg", ".m4a", ".wma", ".opus", ".mka"],
    "Documents": [".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".txt", ".epub", ".csv", ".rtf", ".odt"],
    "Compressed": [".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".iso", ".tgz"],
    "Programs": [".exe", ".msi", ".bat", ".cmd", ".apk", ".dmg", ".appimage", ".jar", ".ps1"],
    "Images": [".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg", ".ico", ".tiff"]
}


def get_file_category(filename: str) -> str:
    """Return category name or 'Other' based on file extension."""
    ext = os.path.splitext(filename)[1].lower()
    for cat, exts in CATEGORY_MAP.items():
        if ext in exts:
            return cat
    return "Other"


def compute_smart_save_path(base_dir: str, filename: str, smart_routing_enabled: bool = True) -> str:
    """
    Computes absolute save path. If smart routing is enabled,
    automatically nests into the appropriate category folder.
    """
    if not smart_routing_enabled or not filename:
        return os.path.join(base_dir, filename)

    cat = get_file_category(filename)
    if cat != "Other":
        target_dir = os.path.join(base_dir, cat)
    else:
        target_dir = base_dir

    try:
        os.makedirs(target_dir, exist_ok=True)
    except Exception:
        target_dir = base_dir

    return os.path.join(target_dir, filename)


# ----------------------------------------------------------------------
# 2. File Checksum & Integrity
# ----------------------------------------------------------------------

def calculate_checksums(filepath: str, progress_callback: Optional[Callable[[int], None]] = None) -> Dict[str, str]:
    """
    Computes MD5, SHA-1, and SHA-256 for a file in chunks.
    Returns dict: {'md5': '...', 'sha1': '...', 'sha256': '...', 'size': int}
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    total_size = os.path.getsize(filepath)
    hasher_md5 = hashlib.md5()
    hasher_sha1 = hashlib.sha1()
    hasher_sha256 = hashlib.sha256()

    read_bytes = 0
    chunk_size = 128 * 1024  # 128 KB buffer

    with open(filepath, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            hasher_md5.update(chunk)
            hasher_sha1.update(chunk)
            hasher_sha256.update(chunk)
            read_bytes += len(chunk)
            if progress_callback and total_size > 0:
                pct = int((read_bytes / total_size) * 100)
                progress_callback(pct)

    return {
        "md5": hasher_md5.hexdigest().lower(),
        "sha1": hasher_sha1.hexdigest().lower(),
        "sha256": hasher_sha256.hexdigest().lower(),
        "size": total_size
    }


# ----------------------------------------------------------------------
# 3. Antivirus & Archive Automation
# ----------------------------------------------------------------------

def run_windows_defender_scan(filepath: str) -> tuple[bool, str]:
    """
    Invokes Microsoft Defender command-line scanner (MpCmdRun.exe)
    on the specified file.
    Returns (clean: bool, output_message: str).
    """
    if not os.path.exists(filepath):
        return False, f"File does not exist: {filepath}"
    if sys.platform != "win32":
        return False, "Windows Defender scanning is available only on Windows."

    # Common locations for MpCmdRun.exe
    possible_paths = [
        r"C:\Program Files\Windows Defender\MpCmdRun.exe",
        r"C:\ProgramData\Microsoft\Windows Defender\Platform"
    ]

    mp_exe = None
    if os.path.exists(possible_paths[0]):
        mp_exe = possible_paths[0]
    elif os.path.exists(possible_paths[1]):
        # Find latest platform subfolder
        try:
            subdirs = sorted(os.listdir(possible_paths[1]), reverse=True)
            for s in subdirs:
                cand = os.path.join(possible_paths[1], s, "MpCmdRun.exe")
                if os.path.exists(cand):
                    mp_exe = cand
                    break
        except Exception:
            pass

    if not mp_exe:
        # Fallback to powershell Start-MpScan
        ps_cmd = f"Start-MpScan -ScanPath '{filepath}' -ScanType Custom -ErrorAction SilentlyContinue"
        try:
            res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], 
                                 capture_output=True, text=True, timeout=60)
            if res.returncode == 0:
                return True, "PowerShell Defender scan completed. No threats detected."
            return False, f"PowerShell scan returned code {res.returncode}"
        except Exception as e:
            return False, f"Defender scanner executable not found ({e})"

    try:
        # MpCmdRun.exe -Scan -ScanType 3 -File "<filepath>"
        cmd = [mp_exe, "-Scan", "-ScanType", "3", "-File", filepath, "-DisableRemediation"]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        # Return codes: 0 = No threat found, 2 = Threat found
        if res.returncode == 0:
            return True, "Scan Complete: No threats found."
        elif res.returncode == 2:
            return False, "THREAT DETECTED: Windows Defender flagged this file!"
        else:
            return True, f"Defender finished (code {res.returncode}): {res.stdout.strip()[:100]}"
    except subprocess.TimeoutExpired:
        return False, "Defender scan timed out."
    except Exception as e:
        return False, f"Defender invocation error: {e}"


def is_extractable_archive(filepath: str) -> bool:
    """Checks if file is a supported archive type."""
    ext = os.path.splitext(filepath)[1].lower()
    return ext in [".zip", ".tar", ".gz", ".bz2", ".xz", ".tgz"]


def extract_archive_safe(filepath: str, destination_dir: Optional[str] = None) -> tuple[bool, str]:
    """
    Safely extracts a supported archive into destination_dir (or a subfolder next to archive).
    Includes directory traversal protection (Zip Slip prevention).
    """
    if not os.path.exists(filepath):
        return False, f"Archive not found: {filepath}"

    if not destination_dir:
        base_name = os.path.splitext(os.path.basename(filepath))[0]
        destination_dir = os.path.join(os.path.dirname(filepath), f"{base_name}_extracted")

    os.makedirs(destination_dir, exist_ok=True)
    real_dest = os.path.realpath(destination_dir)

    try:
        if zipfile.is_zipfile(filepath):
            with zipfile.ZipFile(filepath, "r") as zf:
                for member in zf.infolist():
                    target_path = os.path.realpath(os.path.join(destination_dir, member.filename))
                    if not target_path.startswith(real_dest):
                        return False, "Extraction aborted: Directory traversal vulnerability detected in archive."
                zf.extractall(destination_dir)
            return True, f"Successfully extracted to: {destination_dir}"

        elif tarfile.is_tarfile(filepath):
            with tarfile.open(filepath, "r:*") as tf:
                for member in tf.getmembers():
                    target_path = os.path.realpath(os.path.join(destination_dir, member.name))
                    if not target_path.startswith(real_dest):
                        return False, "Extraction aborted: Directory traversal vulnerability detected in archive."
                tf.extractall(destination_dir)
            return True, f"Successfully extracted to: {destination_dir}"

        else:
            return False, "Unsupported archive format."
    except Exception as e:
        return False, f"Extraction failed: {e}"


# ----------------------------------------------------------------------
# 4. Site Grabber & HTML Link Crawler
# ----------------------------------------------------------------------

class SiteGrabberCrawler:
    """
    Recursively crawls web pages to capture downloadable files matching criteria.
    """
    def __init__(self, start_url: str, depth: int = 1, 
                 categories: Optional[List[str]] = None,
                 custom_extensions: Optional[List[str]] = None,
                 max_links: int = 200,
                 headers: Optional[Dict[str, str]] = None):
        self.start_url = start_url.strip()
        self.depth = max(1, min(depth, 3))
        self.categories = set(categories) if categories else set(CATEGORY_MAP.keys())
        self.custom_extensions = set(e.lower() if e.startswith(".") else f".{e.lower()}" for e in (custom_extensions or []))
        self.max_links = max_links
        self.headers = headers or {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        }
        self.visited_urls = set()
        self.captured_items = []

    def _match_category(self, ext: str) -> Optional[str]:
        ext = ext.lower()
        if self.custom_extensions and ext in self.custom_extensions:
            return "Custom"
        for cat in self.categories:
            if ext in CATEGORY_MAP.get(cat, []):
                return cat
        return None

    def crawl(self, progress_callback: Optional[Callable[[str, int], None]] = None) -> List[Dict[str, Any]]:
        parsed_root = urllib.parse.urlparse(self.start_url)
        if not parsed_root.scheme or not parsed_root.netloc:
            raise ValueError("Invalid target URL. Must include http:// or https://")

        root_domain = parsed_root.netloc.lower()
        to_visit = [(self.start_url, 1)]
        seen_download_urls = set()

        while to_visit and len(self.captured_items) < self.max_links:
            current_url, current_depth = to_visit.pop(0)
            if current_url in self.visited_urls:
                continue
            self.visited_urls.add(current_url)

            if progress_callback:
                progress_callback(f"Scanning: {current_url[:60]}...", len(self.captured_items))

            try:
                req = urllib.request.Request(current_url, headers=self.headers)
                with urllib.request.urlopen(req, timeout=12) as resp:
                    c_type = resp.headers.get("Content-Type", "").lower()
                    if "text/html" not in c_type and "application/xhtml" not in c_type:
                        # Direct file encountered as target URL
                        ext = os.path.splitext(urllib.parse.urlparse(current_url).path)[1].lower()
                        cat = self._match_category(ext)
                        if cat and current_url not in seen_download_urls:
                            seen_download_urls.add(current_url)
                            fn = os.path.basename(urllib.parse.urlparse(current_url).path) or "download"
                            self.captured_items.append({
                                "url": current_url,
                                "filename": fn,
                                "category": cat,
                                "extension": ext,
                                "source_page": current_url
                            })
                        continue

                    html_bytes = resp.read(2 * 1024 * 1024)  # Read up to 2MB HTML
                    html_text = html_bytes.decode("utf-8", errors="ignore")
            except Exception:
                continue

            soup = BeautifulSoup(html_text, "html.parser")

            # Extract downloadable resources from tags: <a>, <img>, <video>, <audio>, <source>
            candidate_links = []

            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"].strip()
                abs_url = urllib.parse.urljoin(current_url, href)
                candidate_links.append((abs_url, "link"))

            for img_tag in soup.find_all("img", src=True):
                src = img_tag["src"].strip()
                abs_url = urllib.parse.urljoin(current_url, src)
                candidate_links.append((abs_url, "image"))

            for media_tag in soup.find_all(["video", "audio", "source"], src=True):
                src = media_tag["src"].strip()
                abs_url = urllib.parse.urljoin(current_url, src)
                candidate_links.append((abs_url, "media"))

            for link_url, tag_type in candidate_links:
                parsed_link = urllib.parse.urlparse(link_url)
                if parsed_link.scheme not in ("http", "https"):
                    continue

                path_clean = parsed_link.path.strip()
                ext = os.path.splitext(path_clean)[1].lower()
                cat = self._match_category(ext)

                if cat:
                    if link_url not in seen_download_urls:
                        seen_download_urls.add(link_url)
                        fn = os.path.basename(path_clean) or f"resource_{len(self.captured_items)+1}{ext}"
                        self.captured_items.append({
                            "url": link_url,
                            "filename": fn,
                            "category": cat,
                            "extension": ext,
                            "source_page": current_url
                        })
                        if len(self.captured_items) >= self.max_links:
                            break
                elif current_depth < self.depth:
                    # Queue internal links on the same domain for deeper crawl
                    if parsed_link.netloc.lower() == root_domain:
                        if link_url not in self.visited_urls and not any(link_url == u for u, d in to_visit):
                            # Skip common non-crawlable anchors
                            if not ext or ext in [".html", ".htm", ".php", ".asp", ".aspx"]:
                                to_visit.append((link_url, current_depth + 1))

        return self.captured_items
