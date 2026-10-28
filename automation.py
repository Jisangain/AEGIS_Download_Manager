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
import ntpath
import re
import sys
import shutil
import hashlib
import stat
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
        # Pass the target through the environment so path text is never parsed as PowerShell code.
        ps_cmd = (
            "$ErrorActionPreference = 'Stop'; "
            "try { Start-MpScan -ScanPath $env:AEGIS_SCAN_TARGET "
            "-ScanType Custom -ErrorAction Stop; exit 0 } catch { exit 1 }"
        )
        scan_env = os.environ.copy()
        scan_env["AEGIS_SCAN_TARGET"] = os.path.abspath(filepath)
        try:
            res = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                timeout=60,
                env=scan_env,
            )
            if res.returncode == 0:
                return False, "Defender scan ran, but this fallback cannot verify whether threats were found."
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
            return False, f"Defender scan result is inconclusive (code {res.returncode})."
    except subprocess.TimeoutExpired:
        return False, "Defender scan timed out."
    except Exception as e:
        return False, f"Defender invocation error: {e}"


def is_extractable_archive(filepath: str) -> bool:
    """Checks if file is a supported archive type."""
    ext = os.path.splitext(filepath)[1].lower()
    return ext in [".zip", ".tar", ".gz", ".bz2", ".xz", ".tgz"]


def _archive_path_is_within(root: str, path: str) -> bool:
    """Compare path components, avoiding unsafe string-prefix containment checks."""
    try:
        common = os.path.commonpath((root, path))
    except (OSError, ValueError):
        return False
    return os.path.normcase(common) == os.path.normcase(root)


def _archive_member_target(root: str, member_name: str) -> str:
    """Resolve a ZIP/TAR member while rejecting traversal and cross-platform absolute paths."""
    if not isinstance(member_name, str) or not member_name or "\x00" in member_name:
        raise ValueError("Archive contains an invalid member path.")
    if member_name.startswith(("/", "\\")) or ntpath.splitdrive(member_name)[0]:
        raise ValueError("Archive contains an absolute member path.")

    # Treat both separators as path separators so Windows-style traversal is rejected on Linux too.
    parts = [part for part in member_name.replace("\\", "/").split("/") if part not in ("", ".")]
    if any(part == ".." for part in parts):
        raise ValueError("Archive contains a parent-directory traversal path.")

    target = os.path.abspath(os.path.join(root, *parts)) if parts else root
    if not _archive_path_is_within(root, target):
        raise ValueError("Archive member resolves outside the extraction directory.")
    return target


def _verify_archive_target(root: str, target: str) -> None:
    """Reject existing symlink parents/targets that could redirect extraction outside root."""
    if os.path.normcase(os.path.abspath(target)) == os.path.normcase(root):
        return
    parent = os.path.realpath(os.path.dirname(target))
    if not _archive_path_is_within(root, parent):
        raise ValueError("Extraction path traverses a symlink outside the destination.")
    if os.path.islink(target):
        raise ValueError("Extraction would overwrite a symbolic link.")


def extract_archive_safe(filepath: str, destination_dir: Optional[str] = None) -> tuple[bool, str]:
    """
    Safely extracts a supported archive into destination_dir (or a subfolder next to archive).
    Rejects traversal, link entries, and special TAR members before writing files.
    """
    if not os.path.exists(filepath):
        return False, f"Archive not found: {filepath}"

    if not destination_dir:
        base_name = os.path.splitext(os.path.basename(filepath))[0]
        destination_dir = os.path.join(os.path.dirname(filepath), f"{base_name}_extracted")

    try:
        os.makedirs(destination_dir, exist_ok=True)
        real_dest = os.path.realpath(destination_dir)

        if zipfile.is_zipfile(filepath):
            with zipfile.ZipFile(filepath, "r") as zf:
                planned = []
                for member in zf.infolist():
                    target = _archive_member_target(real_dest, member.filename)
                    unix_mode = member.external_attr >> 16
                    if stat.S_ISLNK(unix_mode):
                        raise ValueError("ZIP symbolic-link members are not allowed.")
                    _verify_archive_target(real_dest, target)
                    planned.append((member, target))

                for member, target in planned:
                    if member.is_dir():
                        os.makedirs(target, exist_ok=True)
                        continue
                    os.makedirs(os.path.dirname(target), exist_ok=True)
                    _verify_archive_target(real_dest, target)
                    with zf.open(member, "r") as source, open(target, "wb") as output:
                        shutil.copyfileobj(source, output)
            return True, f"Successfully extracted to: {destination_dir}"

        elif tarfile.is_tarfile(filepath):
            with tarfile.open(filepath, "r:*") as tf:
                planned = []
                for member in tf.getmembers():
                    target = _archive_member_target(real_dest, member.name)
                    if not (member.isdir() or member.isfile()):
                        raise ValueError("TAR links and special-file members are not allowed.")
                    _verify_archive_target(real_dest, target)
                    planned.append((member, target))

                for member, target in planned:
                    if member.isdir():
                        os.makedirs(target, exist_ok=True)
                        continue
                    os.makedirs(os.path.dirname(target), exist_ok=True)
                    _verify_archive_target(real_dest, target)
                    source = tf.extractfile(member)
                    if source is None:
                        raise ValueError("Could not read a regular file from the TAR archive.")
                    with source, open(target, "wb") as output:
                        shutil.copyfileobj(source, output)
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
