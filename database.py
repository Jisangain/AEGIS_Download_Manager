"""
Aegis Download Manager - Database & Settings Layer
SQLite-backed persistence for tasks, categories, and application configuration.
Zero telemetry, zero licensing checks, fully local.
"""

import os
import sqlite3
import threading
from contextlib import contextmanager
from typing import Dict, Any, List, Optional
from datetime import datetime
from platform_paths import app_data_directory

DEFAULT_DOWNLOAD_DIR = os.path.join(os.path.expanduser("~"), "Downloads")

class Database:
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            app_data = app_data_directory()
            self.db_path = os.path.join(app_data, "aegis_downloads.db")
        else:
            self.db_path = db_path
            
        self._lock = threading.RLock()
        self._init_db()

    @contextmanager
    def _connection(self):
        conn = sqlite3.connect(self.db_path, timeout=15.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self):
        with self._lock, self._connection() as conn:
            cursor = conn.cursor()
            # Settings table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            
            # Downloads table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS downloads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    save_path TEXT NOT NULL,
                    total_size INTEGER DEFAULT 0,
                    downloaded_size INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'queued',
                    speed TEXT DEFAULT '',
                    eta TEXT DEFAULT '',
                    category TEXT DEFAULT 'Other',
                    engine_type TEXT DEFAULT 'auto',
                    format_id TEXT DEFAULT '',
                    error_message TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP
                )
            """)
            conn.commit()

            # Migration: ensure scheduled_time and queue_pos exist
            cursor.execute("PRAGMA table_info(downloads)")
            cols = [col[1] for col in cursor.fetchall()]
            if "scheduled_time" not in cols:
                cursor.execute("ALTER TABLE downloads ADD COLUMN scheduled_time TEXT DEFAULT ''")
            if "queue_pos" not in cols:
                cursor.execute("ALTER TABLE downloads ADD COLUMN queue_pos INTEGER DEFAULT 0")

            # Set default settings if not exists
            defaults = {
                "download_dir": DEFAULT_DOWNLOAD_DIR,
                "max_concurrent": "3",
                "default_connections": "16",
                "aria2_path": "",
                "ffmpeg_path": "",
                "auto_resume": "true",
                "theme": "Dark",
                "max_download_speed": "0",
                "clipboard_monitor": "false",
                "smart_routing": "true",
                "auto_antivirus_scan": "false",
                "auto_extract_archives": "false"
            }
            for k, v in defaults.items():
                cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))
            conn.commit()

    def get_setting(self, key: str, default: str = "") -> str:
        with self._lock, self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row["value"] if row else default

    def set_setting(self, key: str, value: str):
        with self._lock, self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
            conn.commit()

    def get_routed_save_path(self, filename: str, base_dir: Optional[str] = None) -> str:
        """Returns smart-routed path in category subfolder if smart_routing setting is enabled."""
        base = base_dir or self.get_setting("download_dir", DEFAULT_DOWNLOAD_DIR)
        smart_on = self.get_setting("smart_routing", "true") == "true"
        if not smart_on or not filename:
            return os.path.join(base, filename)
        
        cat = self.categorize_filename(filename)
        if cat != "Other":
            target_dir = os.path.join(base, cat)
        else:
            target_dir = base
        try:
            os.makedirs(target_dir, exist_ok=True)
        except Exception:
            target_dir = base
        return os.path.join(target_dir, filename)

    def add_download(self, url: str, filename: str, save_path: str, 
                     total_size: int = 0, category: str = "Other",
                     engine_type: str = "auto", format_id: str = "",
                     scheduled_time: str = "") -> int:
        with self._lock, self._connection() as conn:
            cursor = conn.cursor()
            initial_status = "scheduled" if scheduled_time else "queued"
            
            # Auto-route save_path if it was set to plain base dir
            cursor.execute("SELECT value FROM settings WHERE key = 'download_dir'")
            r_dir = cursor.fetchone()
            base_dir = r_dir["value"] if r_dir else DEFAULT_DOWNLOAD_DIR

            cursor.execute("SELECT value FROM settings WHERE key = 'smart_routing'")
            r_smart = cursor.fetchone()
            smart_on = (r_smart["value"] == "true") if r_smart else True

            if smart_on:
                if os.path.dirname(os.path.abspath(save_path)) == os.path.abspath(base_dir):
                    cat_name = self.categorize_filename(filename)
                    if cat_name != "Other":
                        cat_dir = os.path.join(base_dir, cat_name)
                        os.makedirs(cat_dir, exist_ok=True)
                        save_path = os.path.join(cat_dir, filename)

            # Get next queue position
            cursor.execute("SELECT COALESCE(MAX(queue_pos), 0) + 1 AS next_pos FROM downloads")
            next_pos = cursor.fetchone()["next_pos"]

            cursor.execute("""
                INSERT INTO downloads (url, filename, save_path, total_size, category, engine_type, format_id, status, scheduled_time, queue_pos)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (url, filename, save_path, total_size, category, engine_type, format_id, initial_status, scheduled_time, next_pos))
            conn.commit()
            return cursor.lastrowid

    def move_queue(self, task_id: int, direction: str) -> bool:
        """
        Reorders queue priority for task_id ('top', 'up', 'down', 'bottom').
        Returns True if queue changed.
        """
        with self._lock, self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, queue_pos, status FROM downloads WHERE id = ?", (task_id,))
            target = cursor.fetchone()
            if not target or target["status"] != "queued":
                return False

            curr_pos = target["queue_pos"]
            direction = direction.lower()

            if direction == "top":
                cursor.execute("SELECT COALESCE(MIN(queue_pos), 1) - 1 AS new_pos FROM downloads WHERE status = 'queued'")
                new_pos = cursor.fetchone()["new_pos"]
                cursor.execute("UPDATE downloads SET queue_pos = ? WHERE id = ?", (new_pos, task_id))
                conn.commit()
                return True

            elif direction == "bottom":
                cursor.execute("SELECT COALESCE(MAX(queue_pos), 0) + 1 AS new_pos FROM downloads WHERE status = 'queued'")
                new_pos = cursor.fetchone()["new_pos"]
                cursor.execute("UPDATE downloads SET queue_pos = ? WHERE id = ?", (new_pos, task_id))
                conn.commit()
                return True

            elif direction == "up":
                # Find queued item immediately before curr_pos
                cursor.execute("""
                    SELECT id, queue_pos FROM downloads 
                    WHERE status = 'queued' AND queue_pos < ? 
                    ORDER BY queue_pos DESC LIMIT 1
                """, (curr_pos,))
                prev_row = cursor.fetchone()
                if prev_row:
                    prev_id, prev_pos = prev_row["id"], prev_row["queue_pos"]
                    cursor.execute("UPDATE downloads SET queue_pos = ? WHERE id = ?", (prev_pos, task_id))
                    cursor.execute("UPDATE downloads SET queue_pos = ? WHERE id = ?", (curr_pos, prev_id))
                    conn.commit()
                    return True
                return False

            elif direction == "down":
                # Find queued item immediately after curr_pos
                cursor.execute("""
                    SELECT id, queue_pos FROM downloads 
                    WHERE status = 'queued' AND queue_pos > ? 
                    ORDER BY queue_pos ASC LIMIT 1
                """, (curr_pos,))
                next_row = cursor.fetchone()
                if next_row:
                    next_id, next_pos = next_row["id"], next_row["queue_pos"]
                    cursor.execute("UPDATE downloads SET queue_pos = ? WHERE id = ?", (next_pos, task_id))
                    cursor.execute("UPDATE downloads SET queue_pos = ? WHERE id = ?", (curr_pos, next_id))
                    conn.commit()
                    return True
                return False

        return False

    def get_ordered_queued_downloads(self) -> List[Dict[str, Any]]:
        with self._lock, self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM downloads 
                WHERE status = 'queued' 
                ORDER BY queue_pos ASC, id ASC
            """)
            return [dict(row) for row in cursor.fetchall()]

    def set_schedule(self, task_id: int, scheduled_time: str):
        with self._lock, self._connection() as conn:
            cursor = conn.cursor()
            status = "scheduled" if scheduled_time else "queued"
            cursor.execute("""
                UPDATE downloads SET scheduled_time = ?, status = ? WHERE id = ?
            """, (scheduled_time, status, task_id))
            conn.commit()

    def get_due_scheduled_downloads(self) -> List[Dict[str, Any]]:
        with self._lock, self._connection() as conn:
            cursor = conn.cursor()
            now_str = datetime.now().isoformat()
            cursor.execute("""
                SELECT * FROM downloads 
                WHERE status = 'scheduled' AND scheduled_time != '' AND scheduled_time <= ?
                ORDER BY id ASC
            """, (now_str,))
            return [dict(row) for row in cursor.fetchall()]

    def update_progress(self, task_id: int, downloaded: int, total: int, speed: str, eta: str):
        with self._lock, self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE downloads 
                SET downloaded_size = ?, total_size = CASE WHEN ? > 0 THEN ? ELSE total_size END,
                    speed = ?, eta = ?
                WHERE id = ?
            """, (downloaded, total, total, speed, eta, task_id))
            conn.commit()

    def update_status(self, task_id: int, status: str, error_msg: str = ""):
        with self._lock, self._connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat() if status == "completed" else None
            cursor.execute("""
                UPDATE downloads 
                SET status = ?, error_message = ?, completed_at = COALESCE(?, completed_at)
                WHERE id = ?
            """, (status, error_msg, now, task_id))
            conn.commit()

    def get_download(self, task_id: int) -> Optional[Dict[str, Any]]:
        with self._lock, self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM downloads WHERE id = ?", (task_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def update_file_path(self, task_id: int, save_path: str, filename: Optional[str] = None):
        with self._lock, self._connection() as conn:
            cursor = conn.cursor()
            if filename:
                cursor.execute("UPDATE downloads SET save_path = ?, filename = ? WHERE id = ?", (save_path, filename, task_id))
            else:
                cursor.execute("UPDATE downloads SET save_path = ? WHERE id = ?", (save_path, task_id))
            conn.commit()

    def get_all_downloads(self) -> List[Dict[str, Any]]:
        with self._lock, self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM downloads ORDER BY id DESC")
            return [dict(row) for row in cursor.fetchall()]

    def delete_download(self, task_id: int, delete_file: bool = False):
        task = self.get_download(task_id)
        if task and delete_file:
            path = task.get("save_path")
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass
        with self._lock, self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM downloads WHERE id = ?", (task_id,))
            conn.commit()

    @staticmethod
    def categorize_filename(filename: str) -> str:
        ext = os.path.splitext(filename)[1].lower()
        categories = {
            "Video": [".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".3gp"],
            "Audio": [".mp3", ".wav", ".aac", ".flac", ".ogg", ".m4a", ".wma", ".opus"],
            "Documents": [".pdf", ".docx", ".doc", ".xlsx", ".pptx", ".txt", ".epub", ".csv", ".rtf"],
            "Compressed": [".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".iso"],
            "Programs": [".exe", ".msi", ".bat", ".cmd", ".apk", ".dmg", ".appimage"]
        }
        for cat, ext_list in categories.items():
            if ext in ext_list:
                return cat
        return "Other"
