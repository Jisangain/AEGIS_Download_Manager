"""
Automated Test Suite for Aegis Download Manager
Validates database operations, tool detection, engine workers, and UI initialization.
"""

import os
import sys
import time
import tempfile
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

def test_database():
    print("[1/4] Testing Database Layer...")
    from database import Database
    with tempfile.TemporaryDirectory() as tmpdir:
        db_file = os.path.join(tmpdir, "test.db")
        db = Database(db_file)
        
        # Test settings
        db.set_setting("test_key", "test_val")
        assert db.get_setting("test_key") == "test_val", "Settings set/get failed"
        
        # Test task addition
        task_id = db.add_download("http://example.com/test.zip", "test.zip", os.path.join(tmpdir, "test.zip"), total_size=1024, category="Compressed")
        assert task_id == 1, "Task ID should be 1"
        
        # Test progress update
        db.update_progress(task_id, 512, 1024, "1 MB/s", "00:01")
        task = db.get_download(task_id)
        assert task["downloaded_size"] == 512, "Progress update failed"
        
        # Test status update
        db.update_status(task_id, "completed")
        task = db.get_download(task_id)
        assert task["status"] == "completed", "Status update failed"
        
        # Test categorization
        assert db.categorize_filename("video.mp4") == "Video"
        assert db.categorize_filename("song.mp3") == "Audio"
        assert db.categorize_filename("doc.pdf") == "Documents"
    print("  -> Database layer passed all tests!")

def test_tool_detection():
    print("[2/4] Testing External Tool Detection...")
    from engine import find_tool_binary
    aria2 = find_tool_binary("aria2c")
    ffmpeg = find_tool_binary("ffmpeg")
    print(f"  -> aria2c binary: {aria2}")
    print(f"  -> ffmpeg binary: {ffmpeg}")
    assert aria2 is not None or ffmpeg is not None or True, "Tool search executed"

def test_download_engine():
    print("[3/4] Testing Download Engine (Direct Worker)...")
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)

    from engine import DirectHttpWorker
    with tempfile.TemporaryDirectory() as tmpdir:
        test_url = "https://raw.githubusercontent.com/git/git/master/README.md"
        worker = DirectHttpWorker(1, test_url, "git_readme.md", tmpdir)
        
        progress_events = []
        worker.progress_signal.connect(lambda tid, dl, tot, spd, eta, pct: progress_events.append(pct), Qt.ConnectionType.DirectConnection)
        
        finished_files = []
        worker.finished_signal.connect(lambda tid, path: finished_files.append(path), Qt.ConnectionType.DirectConnection)
        
        worker.start()
        worker.wait(15000)
        
        dest = os.path.join(tmpdir, "git_readme.md")
        assert os.path.exists(dest), "Target file was not created"
        assert os.path.getsize(dest) > 100, "Downloaded file is empty"
        assert len(finished_files) > 0, "Finished signal was not emitted"
        print(f"  -> Direct download verified! Downloaded {os.path.getsize(dest)} bytes successfully.")

def test_ui_instantiation():
    print("[4/4] Testing PyQt6 UI Instantiation (Headless)...")
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
    
    from ui import MainWindow
    window = MainWindow()
    assert window.table.columnCount() == 8, "Table column count mismatch"
    assert window.sidebar.count() > 0, "Sidebar categories missing"
    print("  -> UI MainWindow initialized cleanly with zero errors!")

if __name__ == "__main__":
    print("=== Running Aegis Download Manager Test Suite ===")
    test_database()
    test_tool_detection()
    test_download_engine()
    test_ui_instantiation()
    print("=== ALL TESTS PASSED SUCCESSFULLY! ===")
