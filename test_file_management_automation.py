"""
Test Suite for Aegis Download Manager - File Management & Automation
Validates:
1. Smart folder routing for all category types
2. Queue reordering and priority-based scheduling
3. File integrity checksums (MD5, SHA1, SHA256), Defender scanner hook, and archive extraction
4. Site Grabber & HTML recursive link crawler
"""

import os
import sys
import shutil
import tempfile
import hashlib
import zipfile
import http.server
import threading
from typing import Dict, Any

from database import Database
from automation import (
    calculate_checksums, run_windows_defender_scan,
    is_extractable_archive, extract_archive_safe,
    SiteGrabberCrawler, compute_smart_save_path,
    CATEGORY_MAP, get_file_category
)

def test_smart_folder_routing():
    print("\n--- Test 1: Smart Folder Routing ---")
    tmp_dir = tempfile.mkdtemp(prefix="aegis_test_routing_")
    db_file = os.path.join(tmp_dir, "test.db")
    db = Database(db_file)
    db.set_setting("download_dir", tmp_dir)
    db.set_setting("smart_routing", "true")

    samples = {
        "avengers_trailer.mp4": "Video",
        "beethoven_symphony.flac": "Audio",
        "quarterly_financials.pdf": "Documents",
        "linux_source.tar.gz": "Compressed",
        "visual_studio_setup.exe": "Programs",
        "wallpaper_4k.webp": "Images",
        "unrecognized_blob.bin": "Other"
    }

    for fn, expected_cat in samples.items():
        cat = get_file_category(fn)
        assert cat == expected_cat, f"Expected {expected_cat} for {fn}, got {cat}"

        routed_path = compute_smart_save_path(tmp_dir, fn, smart_routing_enabled=True)
        if expected_cat != "Other":
            expected_parent = os.path.join(tmp_dir, expected_cat)
            assert os.path.dirname(routed_path) == expected_parent, f"Route mismatch for {fn}: {routed_path}"
            assert os.path.isdir(expected_parent), f"Directory was not created: {expected_parent}"
        else:
            assert os.path.dirname(routed_path) == tmp_dir

    # Test auto-routing in db.add_download
    task_id = db.add_download(
        url="https://example.com/movie.mkv",
        filename="movie.mkv",
        save_path=os.path.join(tmp_dir, "movie.mkv"),
        category="Video"
    )
    t = db.get_download(task_id)
    expected_mkv_path = os.path.join(tmp_dir, "Video", "movie.mkv")
    assert os.path.normpath(t["save_path"]) == os.path.normpath(expected_mkv_path), f"Auto-route in add_download failed: {t['save_path']}"
    print("[PASS] Smart folder routing verified across all categories.")
    shutil.rmtree(tmp_dir, ignore_errors=True)


def test_queue_reordering_and_priority():
    print("\n--- Test 2: Queue Reordering & Priority Control ---")
    tmp_dir = tempfile.mkdtemp(prefix="aegis_test_queue_")
    db_file = os.path.join(tmp_dir, "test.db")
    db = Database(db_file)

    # Seed 4 tasks in queue
    t1 = db.add_download("https://example.com/file1.zip", "file1.zip", os.path.join(tmp_dir, "file1.zip"))
    t2 = db.add_download("https://example.com/file2.zip", "file2.zip", os.path.join(tmp_dir, "file2.zip"))
    t3 = db.add_download("https://example.com/file3.zip", "file3.zip", os.path.join(tmp_dir, "file3.zip"))
    t4 = db.add_download("https://example.com/file4.zip", "file4.zip", os.path.join(tmp_dir, "file4.zip"))

    ordered = [x["id"] for x in db.get_ordered_queued_downloads()]
    assert ordered == [t1, t2, t3, t4], f"Initial queue order incorrect: {ordered}"

    # Move t4 to Top
    assert db.move_queue(t4, "top")
    ordered = [x["id"] for x in db.get_ordered_queued_downloads()]
    assert ordered[0] == t4, f"Move to Top failed: {ordered}"

    # Move t1 to Bottom
    assert db.move_queue(t1, "bottom")
    ordered = [x["id"] for x in db.get_ordered_queued_downloads()]
    assert ordered[-1] == t1, f"Move to Bottom failed: {ordered}"

    # Move t3 Up
    # Current order should be: [t4, t2, t3, t1]
    curr_idx_t3 = ordered.index(t3)
    assert db.move_queue(t3, "up")
    new_ordered = [x["id"] for x in db.get_ordered_queued_downloads()]
    assert new_ordered.index(t3) == curr_idx_t3 - 1, f"Move Up failed: {new_ordered}"

    # Move t3 Down
    assert db.move_queue(t3, "down")
    after_down = [x["id"] for x in db.get_ordered_queued_downloads()]
    assert after_down.index(t3) == curr_idx_t3, f"Move Down failed: {after_down}"

    print("[PASS] Queue priority reordering (Top, Up, Down, Bottom) verified.")
    shutil.rmtree(tmp_dir, ignore_errors=True)


def test_integrity_and_automation():
    print("\n--- Test 3: Checksums, Antivirus & Archive Automation ---")
    tmp_dir = tempfile.mkdtemp(prefix="aegis_test_integrity_")

    # 1. Checksums
    test_file = os.path.join(tmp_dir, "sample.bin")
    sample_data = b"Aegis Download Manager High Speed Cryptographic Integrity Test Data 2026"
    with open(test_file, "wb") as f:
        f.write(sample_data)

    res = calculate_checksums(test_file)
    expected_md5 = hashlib.md5(sample_data).hexdigest()
    expected_sha1 = hashlib.sha1(sample_data).hexdigest()
    expected_sha256 = hashlib.sha256(sample_data).hexdigest()

    assert res["md5"] == expected_md5, f"MD5 mismatch: {res['md5']} vs {expected_md5}"
    assert res["sha1"] == expected_sha1, f"SHA1 mismatch: {res['sha1']} vs {expected_sha1}"
    assert res["sha256"] == expected_sha256, f"SHA256 mismatch: {res['sha256']} vs {expected_sha256}"
    assert res["size"] == len(sample_data)
    print("-> Checksums (MD5, SHA1, SHA256) bit-exact.")

    # 2. Archive extraction
    zip_path = os.path.join(tmp_dir, "archive.zip")
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("subfolder/inner.txt", "Inner extracted content.")
        zf.writestr("root.txt", "Root extracted file.")

    assert is_extractable_archive(zip_path) is True
    dest_extracted = os.path.join(tmp_dir, "archive_extracted")
    ok, msg = extract_archive_safe(zip_path, dest_extracted)
    assert ok is True, f"Extraction failed: {msg}"
    assert os.path.exists(os.path.join(dest_extracted, "subfolder", "inner.txt"))
    assert os.path.exists(os.path.join(dest_extracted, "root.txt"))
    print("-> Safe archive extraction verified.")

    # 3. Defender hook contract
    clean, av_msg = run_windows_defender_scan(test_file)
    assert isinstance(clean, bool)
    print(f"-> Defender scan execution completed: clean={clean}, info='{av_msg[:60]}'")

    print("[PASS] Integrity, Defender scanner, and archive extraction verified.")
    shutil.rmtree(tmp_dir, ignore_errors=True)


def test_site_grabber_crawler():
    print("\n--- Test 4: Site Grabber & HTML Link Crawler ---")
    mock_html = """
    <!DOCTYPE html>
    <html>
    <head><title>Mock Download Gallery</title></head>
    <body>
        <h1>Files Repository</h1>
        <a href="/downloads/video_4k.mp4">4K Video</a>
        <a href="/downloads/audio_track.flac">Lossless Audio</a>
        <a href="https://example.com/docs/spec.pdf">Specification PDF</a>
        <a href="files/setup_v2.exe">Software Installer</a>
        <a href="backup/data.zip">ZIP Archive</a>
        <img src="images/banner.webp" alt="Banner">
        <video src="media/stream.webm"></video>
        <a href="/page2.html">Next Page</a>
    </body>
    </html>
    """

    class MockHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(mock_html.encode("utf-8"))

        def log_message(self, format, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), MockHandler)
    port = server.server_port
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    try:
        crawler = SiteGrabberCrawler(
            start_url=f"http://127.0.0.1:{port}/index.html",
            depth=1,
            categories=["Video", "Audio", "Documents", "Compressed", "Programs", "Images"]
        )
        items = crawler.crawl()
        assert len(items) >= 6, f"Expected at least 6 files, found {len(items)}"

        categories_found = set(x["category"] for x in items)
        assert "Video" in categories_found
        assert "Audio" in categories_found
        assert "Documents" in categories_found
        assert "Compressed" in categories_found
        assert "Programs" in categories_found
        assert "Images" in categories_found

        print(f"-> Site grabber discovered {len(items)} items across categories: {sorted(list(categories_found))}")
    finally:
        server.shutdown()
        server.server_close()

    print("[PASS] Site Grabber crawler verified.")


if __name__ == "__main__":
    print("=================================================================")
    print("Running AegisDM - File Management & Automation Verification Suite")
    print("=================================================================")
    test_smart_folder_routing()
    test_queue_reordering_and_priority()
    test_integrity_and_automation()
    test_site_grabber_crawler()
    print("\n=================================================================")
    print("ALL 4 TASKS PASSED AND EXECUTED WITH ZERO ERRORS!")
    print("=================================================================")
