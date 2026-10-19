"""
Aegis Download Manager - Modern PyQt6 User Interface
Dark mode, responsive table, category filter, and zero licensing popups.
"""

import os
import sys
import subprocess
import urllib.parse
import threading
import shutil
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTableWidget, QTableWidgetItem, QHeaderView, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QLineEdit, QFileDialog, QDialog, QComboBox,
    QSpinBox, QProgressBar, QMessageBox, QMenu, QToolBar, QStatusBar,
    QCheckBox, QDateTimeEdit, QTextEdit, QStackedWidget, QFrame
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QTimer, QDateTime, QThread
from PyQt6.QtGui import QIcon, QFont, QColor, QAction, QKeySequence, QClipboard, QGuiApplication

from database import Database
from engine import (
    UrlAnalyzerThread, Aria2Worker, YtDlpWorker, DirectHttpWorker,
    find_tool_binary, prevent_sleep, allow_sleep, is_media_stream_url
)
from ipc_server import AegisIpcServer
from automation import (
    calculate_checksums, run_windows_defender_scan,
    is_extractable_archive, extract_archive_safe,
    SiteGrabberCrawler, compute_smart_save_path,
    CATEGORY_MAP, get_file_category
)

def format_file_size(size_bytes: int) -> str:
    """Formats bytes into human readable KB, MB or GB string."""
    if size_bytes <= 0:
        return "--"
    if size_bytes >= 1073741824:
        return f"{size_bytes / (1024**3):.2f} GB"
    if size_bytes >= 1048576:
        return f"{size_bytes / (1024**2):.2f} MB"
    if size_bytes >= 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes} B"


def format_size_pair(downloaded: int, total: int, status: str = "") -> str:
    """Formats downloaded and total sizes into visual display e.g. '120.50 MB / 500.00 MB'."""
    s = (status or "").lower()
    if s == "completed":
        return format_file_size(total if total > 0 else downloaded)
    if downloaded > 0 and total > 0:
        return f"{format_file_size(downloaded)} / {format_file_size(total)}"
    if downloaded > 0 and total <= 0:
        return f"{format_file_size(downloaded)} / --"
    if total > 0:
        return f"0 MB / {format_file_size(total)}" if s == "downloading" else format_file_size(total)
    return "--"


def format_progress_text(pct: float, downloaded: int, total: int, status: str = "") -> str:
    """Returns visual progress bar text with percentage and numbers."""
    s = (status or "").lower()
    if s == "completed" or pct >= 100.0:
        sz = format_file_size(total if total > 0 else downloaded)
        return f"100% ({sz})" if sz != "--" else "100%"
    if total > 0 and downloaded > 0:
        return f"{pct:.1f}% ({format_file_size(downloaded)} / {format_file_size(total)})"
    if downloaded > 0:
        return f"{pct:.1f}% ({format_file_size(downloaded)})"
    return f"{pct:.1f}%"



def get_category_icon(filename: str) -> str:
    return ""

def format_status(status: str) -> tuple[str, str]:
    """Returns (display_text, hex_color)."""
    s = (status or "").lower()
    if s == "completed":
        return "Completed", "#10B981"
    elif s == "downloading":
        return "Downloading", "#38BDF8"
    elif s == "paused":
        return "Paused", "#F59E0B"
    elif s == "scheduled":
        return "Scheduled", "#A78BFA"
    elif s == "queued":
        return "Queued", "#94A3B8"
    elif s == "failed":
        return "Failed", "#F87171"
    elif s == "cancelled":
        return "Cancelled", "#64748B"
    return status.capitalize(), "#94A3B8"

def style_progress_bar(pbar: QProgressBar, status: str):
    s = (status or "").lower()
    if s == "completed":
        chunk_color = "#10B981"
    elif s == "downloading":
        chunk_color = "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #007AFF, stop:1 #38BDF8)"
    elif s == "paused":
        chunk_color = "#F59E0B"
    elif s == "scheduled":
        chunk_color = "#8B5CF6"
    elif s == "failed":
        chunk_color = "#EF4444"
    else:
        chunk_color = "#475569"

    pbar.setStyleSheet(f"""
        QProgressBar {{
            background-color: #18181B;
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 6px;
            text-align: center;
            color: #FFFFFF;
            font-size: 10px;
            font-weight: 600;
            min-height: 16px;
            max-height: 16px;
        }}
        QProgressBar::chunk {{
            background: {chunk_color};
            border-radius: 5px;
        }}
    """)

def format_download_date(date_str: str) -> str:
    if not date_str:
        return "--"
    cleaned = str(date_str).replace("T", " ")
    if "." in cleaned:
        cleaned = cleaned.split(".")[0]
    parts = cleaned.strip().split()
    if len(parts) == 2:
        time_part = ":".join(parts[1].split(":")[:2])
        return f"{parts[0]} {time_part}"
    return cleaned

DARK_STYLESHEET = """
QWidget {
    color: #F1F5F9;
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Arial, sans-serif;
    font-size: 12px;
}
QMainWindow, QDialog {
    background-color: #18181B;
    color: #F1F5F9;
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Arial, sans-serif;
    font-size: 12px;
}
QLabel {
    color: #F1F5F9;
    background-color: transparent;
    font-size: 12px;
}
QCheckBox {
    color: #CBD5E1;
    background-color: transparent;
    spacing: 8px;
    font-size: 12px;
}
QCheckBox::indicator {
    width: 15px;
    height: 15px;
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 4px;
    background-color: rgba(0, 0, 0, 0.35);
}
QCheckBox::indicator:hover {
    border: 1px solid #007AFF;
    background-color: rgba(255, 255, 255, 0.08);
}
QCheckBox::indicator:checked {
    background-color: #007AFF;
    border: 1px solid #0062CC;
}
QGroupBox {
    color: #F1F5F9;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 10px;
    margin-top: 12px;
    padding-top: 12px;
    background-color: rgba(24, 24, 27, 0.5);
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 6px;
    color: #007AFF;
    font-weight: 600;
}
QToolBar {
    background-color: #242429;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    padding: 6px 12px;
    spacing: 5px;
}
QToolButton {
    background-color: transparent;
    color: #CBD5E1;
    padding: 5px 12px;
    border-radius: 8px;
    font-weight: 500;
    font-size: 12px;
    border: 1px solid transparent;
}
QToolButton:hover {
    background-color: rgba(255, 255, 255, 0.08);
    color: #FFFFFF;
    border: 1px solid rgba(255, 255, 255, 0.06);
}
QToolButton:pressed {
    background-color: #0062CC;
    color: #FFFFFF;
}
QToolButton:checked {
    background-color: rgba(0, 122, 255, 0.2);
    color: #60A5FA;
    border: 1px solid rgba(0, 122, 255, 0.35);
}
QToolButton:disabled {
    color: #475569;
    background-color: transparent;
}
QListWidget {
    background-color: #1E1E23;
    border: none;
    border-right: 1px solid rgba(255, 255, 255, 0.08);
    color: #94A3B8;
    padding: 8px 8px;
    font-size: 12px;
}
QListWidget::item {
    padding: 7px 12px;
    border-radius: 8px;
    margin: 2px 0px;
    font-weight: 500;
}
QListWidget::item:selected {
    background-color: #007AFF;
    color: #FFFFFF;
    font-weight: 600;
}
QListWidget::item:hover:!selected {
    background-color: rgba(255, 255, 255, 0.05);
    color: #F1F5F9;
}
QTableWidget {
    background-color: #1E1E23;
    alternate-background-color: #242429;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 10px;
    gridline-color: rgba(255, 255, 255, 0.04);
    color: #F1F5F9;
    selection-background-color: rgba(0, 122, 255, 0.3);
    selection-color: #FFFFFF;
    font-size: 12px;
}
QTableWidget::item {
    padding: 6px 10px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}
QTableWidget::item:selected {
    background-color: rgba(0, 122, 255, 0.35);
    color: #FFFFFF;
}
QHeaderView::section {
    background-color: #18181B;
    color: #94A3B8;
    padding: 8px 10px;
    border: none;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    border-right: 1px solid rgba(255, 255, 255, 0.08);
    font-weight: 600;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
QHeaderView::section:hover {
    background-color: #242429;
    color: #F8FAFC;
}
QSplitter::handle:horizontal {
    width: 3px;
    background-color: rgba(255, 255, 255, 0.06);
}
QSplitter::handle:horizontal:hover {
    background-color: #007AFF;
}
QLineEdit, QComboBox, QSpinBox, QDateTimeEdit {
    background-color: rgba(0, 0, 0, 0.4);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 8px;
    padding: 6px 10px;
    color: #F8FAFC;
    font-size: 12px;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDateTimeEdit:focus {
    border: 1px solid #007AFF;
    background-color: rgba(0, 0, 0, 0.55);
}
QPushButton {
    background-color: #007AFF;
    color: #FFFFFF;
    border: none;
    border-radius: 8px;
    padding: 6px 14px;
    font-weight: 500;
    font-size: 12px;
}
QPushButton:hover {
    background-color: #0062CC;
}
QPushButton:pressed {
    background-color: #0051A8;
}
QPushButton:disabled {
    background-color: rgba(255, 255, 255, 0.05);
    color: #475569;
}
QMenu {
    background-color: #242429;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 10px;
    padding: 4px;
    color: #E2E8F0;
    font-size: 12px;
}
QMenu::item {
    padding: 6px 20px 6px 12px;
    border-radius: 6px;
}
QMenu::item:selected {
    background-color: #007AFF;
    color: #FFFFFF;
}
QMenu::item:disabled {
    color: #475569;
}
QMenu::separator {
    height: 1px;
    background-color: rgba(255, 255, 255, 0.08);
    margin: 4px 6px;
}
QStatusBar {
    background-color: #18181B;
    border-top: 1px solid rgba(255, 255, 255, 0.08);
    color: #94A3B8;
    font-size: 11px;
    padding: 3px 10px;
}
QSplitter::handle {
    background-color: rgba(255, 255, 255, 0.06);
    width: 1px;
}
QProgressBar {
    background-color: #18181B;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 6px;
    text-align: center;
    color: #FFFFFF;
    font-size: 10px;
    font-weight: 600;
    min-height: 16px;
    max-height: 16px;
}
"""

class ScheduleDialog(QDialog):
    def __init__(self, parent=None, current_iso: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Schedule Download Start Time")
        self.setStyleSheet(DARK_STYLESHEET)
        self.resize(380, 160)
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        prompt_lbl = QLabel("Set the date and time when this task should automatically begin:")
        prompt_lbl.setStyleSheet("color: #F8FAFC; font-weight: 500;")
        layout.addWidget(prompt_lbl)
        self.dt_edit = QDateTimeEdit(self)
        self.dt_edit.setCalendarPopup(True)
        self.dt_edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        if current_iso:
            self.dt_edit.setDateTime(QDateTime.fromString(current_iso, Qt.DateFormat.ISODate))
        else:
            self.dt_edit.setDateTime(QDateTime.currentDateTime().addSecs(300))
        layout.addWidget(self.dt_edit)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet("background-color: #333842;")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("Set Schedule")
        save_btn.clicked.connect(self.accept)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)

    def get_scheduled_iso(self) -> str:
        return self.dt_edit.dateTime().toString(Qt.DateFormat.ISODate)


class BatchImportDialog(QDialog):
    def __init__(self, parent=None, db: Optional[Database] = None):
        super().__init__(parent)
        self.db = db or Database()
        self.setWindowTitle("Batch URL Import")
        self.setStyleSheet(DARK_STYLESHEET)
        self.resize(760, 500)
        self.added_count = 0
        self._parsed_items: List[Dict[str, Any]] = []
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # File Chooser
        top_layout = QHBoxLayout()
        load_btn = QPushButton("Open .txt File...")
        load_btn.clicked.connect(self._load_file)
        self.file_lbl = QLabel("Load a text file or paste multiple URLs below.")
        self.file_lbl.setStyleSheet("color: #94A3B8;")
        top_layout.addWidget(load_btn)
        top_layout.addWidget(self.file_lbl)
        top_layout.addStretch()
        layout.addLayout(top_layout)

        # Text input / paste area
        self.text_input = QTextEdit()
        self.text_input.setPlaceholderText("Paste URLs here (one URL per line). Lines starting with # are treated as comments.")
        self.text_input.setMaximumHeight(85)
        self.text_input.textChanged.connect(self._parse_urls_from_text)
        layout.addWidget(self.text_input)

        # Save Folder
        save_layout = QHBoxLayout()
        save_lbl = QLabel("Save To:")
        save_lbl.setFixedWidth(60)
        self.save_input = QLineEdit(self.db.get_setting("download_dir", os.path.expanduser("~/Downloads")))
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self._browse_save_dir)
        save_layout.addWidget(save_lbl)
        save_layout.addWidget(self.save_input)
        save_layout.addWidget(browse_btn)
        layout.addLayout(save_layout)

        # Table Preview
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Select", "Status", "Filename", "URL"])
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)

        # Select all / Deselect all / Summary
        ctrl_layout = QHBoxLayout()
        sel_all = QPushButton("Select All Valid")
        sel_all.clicked.connect(self._select_all_valid)
        desel_all = QPushButton("Deselect All")
        desel_all.clicked.connect(self._deselect_all)
        self.summary_lbl = QLabel("0 valid URLs found.")
        self.summary_lbl.setStyleSheet("color: #10B981; font-weight: 500;")
        ctrl_layout.addWidget(sel_all)
        ctrl_layout.addWidget(desel_all)
        ctrl_layout.addSpacing(15)
        ctrl_layout.addWidget(self.summary_lbl)
        ctrl_layout.addStretch()
        layout.addLayout(ctrl_layout)

        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet("background-color: #333842;")
        cancel_btn.clicked.connect(self.reject)
        self.import_btn = QPushButton("Add to Queue (0)")
        self.import_btn.clicked.connect(self._confirm_import)
        self.import_btn.setEnabled(False)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(self.import_btn)
        layout.addLayout(btn_layout)

    def _browse_save_dir(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Destination Folder", self.save_input.text())
        if folder:
            self.save_input.setText(folder)

    def _load_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Text File with URLs", "", "Text Files (*.txt);;All Files (*.*)")
        if not file_path:
            return
        self.file_lbl.setText(f"Loaded: {os.path.basename(file_path)}")
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            self.text_input.setPlainText(content)
        except Exception as e:
            QMessageBox.critical(self, "Read Error", f"Failed to open file: {str(e)}")

    def _parse_urls_from_text(self):
        raw_text = self.text_input.toPlainText()
        lines = raw_text.splitlines()
        self._parsed_items = []
        valid_count = 0

        for line in lines:
            line_str = line.strip()
            if not line_str or line_str.startswith("#"):
                continue

            parsed = urllib.parse.urlparse(line_str)
            is_valid = parsed.scheme in ("http", "https") and bool(parsed.netloc)
            path_part = parsed.path.rstrip("/")
            raw_fname = os.path.basename(path_part) if path_part else "download.bin"
            clean_fname = raw_fname.split("?")[0] if raw_fname else "download.bin"

            item = {
                "url": line_str,
                "is_valid": is_valid,
                "filename": clean_fname,
                "status": "Valid" if is_valid else "Invalid Scheme/Host"
            }
            if is_valid:
                valid_count += 1
            self._parsed_items.append(item)

        self._render_table()

    def _render_table(self):
        self.table.setRowCount(len(self._parsed_items))
        valid_selected = 0

        for row, item in enumerate(self._parsed_items):
            chk_item = QTableWidgetItem()
            chk_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            if item["is_valid"]:
                chk_item.setCheckState(Qt.CheckState.Checked)
                valid_selected += 1
            else:
                chk_item.setCheckState(Qt.CheckState.Unchecked)
                chk_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable)

            status_item = QTableWidgetItem(item["status"])
            status_item.setForeground(QColor("#10B981" if item["is_valid"] else "#EF4444"))
            fn_item = QTableWidgetItem(item["filename"])
            url_item = QTableWidgetItem(item["url"])

            self.table.setItem(row, 0, chk_item)
            self.table.setItem(row, 1, status_item)
            self.table.setItem(row, 2, fn_item)
            self.table.setItem(row, 3, url_item)

        self._update_summary()

    def _select_all_valid(self):
        for row in range(self.table.rowCount()):
            if row < len(self._parsed_items) and self._parsed_items[row]["is_valid"]:
                item = self.table.item(row, 0)
                if item:
                    item.setCheckState(Qt.CheckState.Checked)
        self._update_summary()

    def _deselect_all(self):
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item:
                item.setCheckState(Qt.CheckState.Unchecked)
        self._update_summary()

    def _update_summary(self):
        checked_valid = 0
        total_valid = sum(1 for x in self._parsed_items if x["is_valid"])
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.checkState() == Qt.CheckState.Checked:
                if row < len(self._parsed_items) and self._parsed_items[row]["is_valid"]:
                    checked_valid += 1

        self.summary_lbl.setText(f"Found {len(self._parsed_items)} lines ({total_valid} valid URLs). {checked_valid} selected.")
        self.import_btn.setText(f"Add to Queue ({checked_valid})")
        self.import_btn.setEnabled(checked_valid > 0)

    def _confirm_import(self):
        save_dir = self.save_input.text().strip() or self.db.get_setting("download_dir", os.path.expanduser("~/Downloads"))
        os.makedirs(save_dir, exist_ok=True)
        self.added_count = 0

        for row in range(self.table.rowCount()):
            chk = self.table.item(row, 0)
            if chk and chk.checkState() == Qt.CheckState.Checked:
                if row < len(self._parsed_items) and self._parsed_items[row]["is_valid"]:
                    entry = self._parsed_items[row]
                    url = entry["url"]
                    fn = entry["filename"]
                    save_path = os.path.join(save_dir, fn)
                    cat = Database.categorize_filename(fn)
                    self.db.add_download(
                        url=url,
                        filename=fn,
                        save_path=save_path,
                        category=cat,
                        engine_type="auto"
                    )
                    self.added_count += 1

def force_foreground_window(hwnd: int):
    """Brings a window to the top of the Z-order and into foreground across Windows processes."""
    if sys.platform != "win32":
        return
    try:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        user32.AllowSetForegroundWindow(-1)
        fg_hwnd = user32.GetForegroundWindow()
        fg_thread = user32.GetWindowThreadProcessId(fg_hwnd, None)
        cur_thread = kernel32.GetCurrentThreadId()
        attached = False
        if fg_thread != 0 and fg_thread != cur_thread:
            attached = bool(user32.AttachThreadInput(cur_thread, fg_thread, True))
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0040)  # HWND_TOPMOST, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW
        user32.SetForegroundWindow(hwnd)
        user32.BringWindowToTop(hwnd)
        user32.SetFocus(hwnd)
        # Reset topmost to regular top so it doesn't freeze permanently on top of all desktops
        user32.SetWindowPos(hwnd, -2, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0040)  # HWND_NOTOPMOST
        if attached:
            user32.AttachThreadInput(cur_thread, fg_thread, False)
    except Exception:
        pass


class AddDownloadDialog(QDialog):
    def __init__(self, parent=None, db: Optional[Database] = None):
        super().__init__(parent)
        self.db = db or Database()
        self.setWindowTitle("Add New Download")
        self.setStyleSheet(DARK_STYLESHEET)
        self.resize(580, 400)
        self.analyzer_thread: Optional[UrlAnalyzerThread] = None
        self.analyzed_result: Dict[str, Any] = {}
        self.preferred_format_id: str = ""
        self._init_ui()
        self._check_clipboard()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        self.url_layout = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Paste download link (HTTP, HTTPS, YouTube, direct file...)")
        self.url_debounce_timer = QTimer(self)
        self.url_debounce_timer.setSingleShot(True)
        self.url_debounce_timer.setInterval(450)
        self.url_debounce_timer.timeout.connect(self._analyze_url)
        self.url_input.textChanged.connect(self._on_url_input_changed)
        self.analyze_btn = QPushButton("Analyze Link")
        self.analyze_btn.clicked.connect(self._analyze_url)
        self.url_layout.addWidget(self.url_input)
        self.url_layout.addWidget(self.analyze_btn)
        layout.addLayout(self.url_layout)

        # Status / Feedback label
        self.status_lbl = QLabel("Enter a URL and click Analyze, or start direct download.")
        self.status_lbl.setStyleSheet("color: #94A3B8; font-size: 11px;")
        layout.addWidget(self.status_lbl)

        # Filename input
        fn_layout = QHBoxLayout()
        fn_lbl = QLabel("File Name:")
        fn_lbl.setStyleSheet("color: #F8FAFC; font-weight: 500; font-size: 12px;")
        fn_lbl.setFixedWidth(80)
        self.filename_input = QLineEdit()
        fn_layout.addWidget(fn_lbl)
        fn_layout.addWidget(self.filename_input)
        layout.addLayout(fn_layout)

        # Save Directory input
        save_layout = QHBoxLayout()
        save_lbl = QLabel("Save To:")
        save_lbl.setStyleSheet("color: #F8FAFC; font-weight: 500; font-size: 12px;")
        save_lbl.setFixedWidth(80)
        self.save_input = QLineEdit()
        self.save_input.setText(self.db.get_setting("download_dir", os.path.expanduser("~/Downloads")))
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self._browse_folder)
        save_layout.addWidget(save_lbl)
        save_layout.addWidget(self.save_input)
        save_layout.addWidget(browse_btn)
        layout.addLayout(save_layout)

        # Format selector (for media streams)
        fmt_layout = QHBoxLayout()
        fmt_lbl = QLabel("Quality:")
        fmt_lbl.setStyleSheet("color: #F8FAFC; font-weight: 500; font-size: 12px;")
        fmt_lbl.setFixedWidth(80)
        self.format_combo = QComboBox()
        self.format_combo.setEnabled(False)
        self.format_combo.setMaxVisibleItems(16)
        self.format_combo.currentIndexChanged.connect(self._on_format_changed)
        fmt_layout.addWidget(fmt_lbl)
        fmt_layout.addWidget(self.format_combo)
        layout.addLayout(fmt_layout)

        # Connections / Segments
        conn_layout = QHBoxLayout()
        conn_lbl = QLabel("Connections:")
        conn_lbl.setStyleSheet("color: #F8FAFC; font-weight: 500; font-size: 12px;")
        conn_lbl.setFixedWidth(80)
        self.conn_spin = QSpinBox()
        self.conn_spin.setRange(1, 32)
        self.conn_spin.setValue(int(self.db.get_setting("default_connections", "16")))
        conn_layout.addWidget(conn_lbl)
        conn_layout.addWidget(self.conn_spin)
        conn_layout.addStretch()
        layout.addLayout(conn_layout)

        # Schedule Download option
        sched_layout = QHBoxLayout()
        self.schedule_chk = QCheckBox("Schedule for Later:")
        self.schedule_chk.setStyleSheet("color: #F8FAFC; font-weight: 500; font-size: 12px;")
        self.schedule_chk.setFixedWidth(140)
        self.schedule_dt = QDateTimeEdit(QDateTime.currentDateTime().addSecs(300))
        self.schedule_dt.setCalendarPopup(True)
        self.schedule_dt.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.schedule_dt.setEnabled(False)
        self.schedule_chk.toggled.connect(self.schedule_dt.setEnabled)
        sched_layout.addWidget(self.schedule_chk)
        sched_layout.addWidget(self.schedule_dt)
        sched_layout.addStretch()
        layout.addLayout(sched_layout)

        layout.addStretch()

        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setStyleSheet("background-color: #333842;")
        self.cancel_btn.clicked.connect(self.reject)
        self.download_btn = QPushButton("Start Download")
        self.download_btn.clicked.connect(self._accept_download)
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.download_btn)
        layout.addLayout(btn_layout)

    def _check_clipboard(self):
        if self.url_input.text().strip():
            return
        cb = QGuiApplication.clipboard().text().strip()
        if cb.startswith("http://") or cb.startswith("https://"):
            self.url_input.setText(cb)
            QTimer.singleShot(150, self._analyze_url)

    def _on_url_input_changed(self, text: str):
        u = text.strip()
        if u.startswith("http://") or u.startswith("https://"):
            if is_media_stream_url(u):
                self.status_lbl.setText("Media stream detected (YouTube/Video). Preparing formats...")
            else:
                self.status_lbl.setText("Analyzing target URL...")
            self.url_debounce_timer.start()

    def _browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Download Folder", self.save_input.text())
        if folder:
            self.save_input.setText(folder)

    def _analyze_url(self):
        url = self.url_input.text().strip()
        if not url or not (url.startswith("http://") or url.startswith("https://")):
            return

        if hasattr(self, "analyzer_thread") and self.analyzer_thread and self.analyzer_thread.isRunning():
            return

        self.analyze_btn.setEnabled(False)
        self.analyze_btn.setText("Probing...")
        if is_media_stream_url(url):
            self.status_lbl.setText("Probing YouTube/media stream (extracting 4K/HD/Audio formats)...")
        else:
            self.status_lbl.setText("Analyzing target URL and extracting stream metadata...")

        tools = {
            "aria2_path": self.db.get_setting("aria2_path", ""),
            "ffmpeg_path": self.db.get_setting("ffmpeg_path", ""),
            "deno_path": self.db.get_setting("deno_path", "")
        }
        self.analyzer_thread = UrlAnalyzerThread(url, tools)
        self.analyzer_thread.analysis_complete.connect(self._on_analysis_done)
        self.analyzer_thread.analysis_failed.connect(self._on_analysis_fail)
        self.analyzer_thread.start()

    def _on_analysis_done(self, result: Dict[str, Any]):
        self.analyzed_result = result
        self.analyze_btn.setEnabled(True)
        self.analyze_btn.setText("Analyze Link")
        fn = result.get("filename", "download")
        self.filename_input.setText(fn)

        # Smart Folder Routing
        if self.db.get_setting("smart_routing", "true") == "true":
            base_dir = self.db.get_setting("download_dir", os.path.expanduser("~/Downloads"))
            routed = self.db.get_routed_save_path(fn, base_dir)
            self.save_input.setText(os.path.dirname(routed))

        formats = result.get("formats", [])
        if formats:
            self.format_combo.blockSignals(True)
            self.format_combo.clear()
            selected_idx = 0
            for idx, f in enumerate(formats):
                self.format_combo.addItem(f["label"], f["id"])
                if self.preferred_format_id:
                    pref_lower = self.preferred_format_id.lower()
                    if f["id"] == self.preferred_format_id or pref_lower in f.get("label", "").lower() or pref_lower in f.get("id", "").lower():
                        selected_idx = idx
            self.format_combo.setCurrentIndex(selected_idx)
            self.format_combo.setEnabled(True)
            self.format_combo.blockSignals(False)
            self._on_format_changed(selected_idx)
            self.status_lbl.setText(f"Media stream detected! Found {len(formats)} quality options (4K, HD, SD, Audio).")
        else:
            self.format_combo.blockSignals(True)
            self.format_combo.clear()
            self.format_combo.setEnabled(False)
            self.format_combo.blockSignals(False)
            size = result.get("filesize", 0)
            if size > 0:
                mb = size / (1024 * 1024)
                self.status_lbl.setText(f"Direct download verified. Size: {mb:.2f} MB")
            else:
                self.status_lbl.setText("Direct download link verified.")

    def _on_format_changed(self, index: int):
        fmt = self.format_combo.currentData()
        if not fmt:
            return
        cur_fn = self.filename_input.text().strip()
        if not cur_fn:
            return
        base_name, _ = os.path.splitext(cur_fn)
        ext = "mp4"
        for f in self.analyzed_result.get("formats", []):
            if f.get("id") == fmt:
                ext = f.get("ext", "mp4")
                break
        new_fn = f"{base_name}.{ext}"
        self.filename_input.setText(new_fn)

        # Smart Folder Routing update on extension change
        if self.db.get_setting("smart_routing", "true") == "true":
            base_dir = self.db.get_setting("download_dir", os.path.expanduser("~/Downloads"))
            routed = self.db.get_routed_save_path(new_fn, base_dir)
            self.save_input.setText(os.path.dirname(routed))

    def _on_analysis_fail(self, err: str):
        self.analyze_btn.setEnabled(True)
        self.analyze_btn.setText("Analyze Link")
        self.status_lbl.setText(f"Analysis note: {err} (Direct download will proceed)")

    def closeEvent(self, event):
        self._cleanup_analyzer()
        super().closeEvent(event)

    def reject(self):
        self._cleanup_analyzer()
        super().reject()

    def accept(self):
        self._cleanup_analyzer()
        super().accept()

    def _cleanup_analyzer(self):
        if hasattr(self, "url_debounce_timer") and self.url_debounce_timer:
            self.url_debounce_timer.stop()
        if hasattr(self, "analyzer_thread") and self.analyzer_thread:
            try:
                self.analyzer_thread.analysis_complete.disconnect()
            except Exception:
                pass
            try:
                self.analyzer_thread.analysis_failed.disconnect()
            except Exception:
                pass

    def _accept_download(self):
        url = self.url_input.text().strip()
        filename = self.filename_input.text().strip()
        save_dir = self.save_input.text().strip()

        if not url:
            QMessageBox.warning(self, "Invalid Input", "Please provide a download URL.")
            return

        if is_media_stream_url(url):
            if not self.analyzed_result.get("engine"):
                self.analyzed_result["engine"] = "ytdlp"
            if filename in ("download.bin", "download"):
                filename = ""

        if not filename and not is_media_stream_url(url):
            filename = "download.bin"
        if not save_dir:
            save_dir = os.path.expanduser("~/Downloads")

        self.accept()

    def get_task_data(self) -> Dict[str, Any]:
        url = self.url_input.text().strip()
        fmt_id = self.format_combo.currentData() if self.format_combo.isEnabled() else ""
        if not fmt_id and is_media_stream_url(url):
            fmt_id = getattr(self, "preferred_format_id", "") or "bestvideo+bestaudio/best"
        engine = self.analyzed_result.get("engine", "")
        if not engine:
            engine = "ytdlp" if is_media_stream_url(url) else "auto"
        scheduled_iso = self.schedule_dt.dateTime().toString(Qt.DateFormat.ISODate) if self.schedule_chk.isChecked() else ""
        fn = self.filename_input.text().strip()
        if not fn:
            fn = "%(title)s.%(ext)s" if is_media_stream_url(url) else "download.bin"
        return {
            "url": url,
            "filename": fn,
            "save_dir": self.save_input.text().strip() or os.path.expanduser("~/Downloads"),
            "format_id": fmt_id,
            "engine": engine,
            "connections": self.conn_spin.value(),
            "scheduled_time": scheduled_iso
        }


class SettingsDialog(QDialog):
    def __init__(self, parent=None, db: Optional[Database] = None):
        super().__init__(parent)
        self.db = db or Database()
        self.setWindowTitle("Settings")
        self.setStyleSheet(DARK_STYLESHEET)
        self.resize(540, 390)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Download directory
        dir_layout = QHBoxLayout()
        dir_lbl = QLabel("Default Folder:")
        dir_lbl.setFixedWidth(110)
        self.dir_input = QLineEdit(self.db.get_setting("download_dir", os.path.expanduser("~/Downloads")))
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self._browse)
        dir_layout.addWidget(dir_lbl)
        dir_layout.addWidget(self.dir_input)
        dir_layout.addWidget(browse_btn)
        layout.addLayout(dir_layout)

        # Max concurrent
        conc_layout = QHBoxLayout()
        conc_lbl = QLabel("Max Active Tasks:")
        conc_lbl.setFixedWidth(110)
        self.conc_spin = QSpinBox()
        self.conc_spin.setRange(1, 10)
        self.conc_spin.setValue(int(self.db.get_setting("max_concurrent", "3")))
        conc_layout.addWidget(conc_lbl)
        conc_layout.addWidget(self.conc_spin)
        conc_layout.addStretch()
        layout.addLayout(conc_layout)

        # Default connections
        conn_layout = QHBoxLayout()
        conn_lbl = QLabel("Connections/Task:")
        conn_lbl.setFixedWidth(110)
        self.conn_spin = QSpinBox()
        self.conn_spin.setRange(1, 32)
        self.conn_spin.setValue(int(self.db.get_setting("default_connections", "16")))
        conn_layout.addWidget(conn_lbl)
        conn_layout.addWidget(self.conn_spin)
        conn_layout.addStretch()
        layout.addLayout(conn_layout)

        # Download Speed Limiter
        speed_layout = QHBoxLayout()
        speed_lbl = QLabel("Speed Limit:")
        speed_lbl.setFixedWidth(110)
        self.speed_spin = QSpinBox()
        self.speed_spin.setRange(0, 1000000)
        self.speed_spin.setSuffix(" KB/s")
        self.speed_spin.setSpecialValueText("Unlimited (0 KB/s)")
        self.speed_spin.setValue(int(self.db.get_setting("max_download_speed", "0")))
        speed_layout.addWidget(speed_lbl)
        speed_layout.addWidget(self.speed_spin)
        speed_layout.addStretch()
        layout.addLayout(speed_layout)

        # Clipboard Monitor Checkbox
        clip_layout = QHBoxLayout()
        self.clip_chk = QCheckBox("Enable Clipboard Link Sniffer (Prompts before adding copied URLs)")
        self.clip_chk.setChecked(self.db.get_setting("clipboard_monitor", "false") == "true")
        clip_layout.addWidget(self.clip_chk)
        layout.addLayout(clip_layout)

        # Smart Folder Routing Checkbox
        smart_layout = QHBoxLayout()
        self.smart_route_chk = QCheckBox("Enable Smart Category Folder Routing (Auto-sort into Video, Audio, Documents, etc.)")
        self.smart_route_chk.setChecked(self.db.get_setting("smart_routing", "true") == "true")
        smart_layout.addWidget(self.smart_route_chk)
        layout.addLayout(smart_layout)

        # Auto Windows Defender Scan Checkbox
        defender_layout = QHBoxLayout()
        self.defender_chk = QCheckBox("Auto-scan completed downloads with Windows Defender")
        self.defender_chk.setChecked(self.db.get_setting("auto_antivirus_scan", "false") == "true")
        defender_layout.addWidget(self.defender_chk)
        layout.addLayout(defender_layout)

        # Auto Extract Archives Checkbox
        extract_layout = QHBoxLayout()
        self.extract_chk = QCheckBox("Auto-extract downloaded ZIP / TAR archives upon completion")
        self.extract_chk.setChecked(self.db.get_setting("auto_extract_archives", "false") == "true")
        extract_layout.addWidget(self.extract_chk)
        layout.addLayout(extract_layout)

        # aria2 path
        aria_layout = QHBoxLayout()
        aria_lbl = QLabel("aria2c Executable:")
        aria_lbl.setFixedWidth(110)
        self.aria_input = QLineEdit(self.db.get_setting("aria2_path", ""))
        self.aria_input.setPlaceholderText("Auto-detected if left empty")
        aria_layout.addWidget(aria_lbl)
        aria_layout.addWidget(self.aria_input)
        layout.addLayout(aria_layout)

        # ffmpeg path
        ff_layout = QHBoxLayout()
        ff_lbl = QLabel("FFmpeg Executable:")
        ff_lbl.setFixedWidth(110)
        self.ff_input = QLineEdit(self.db.get_setting("ffmpeg_path", ""))
        self.ff_input.setPlaceholderText("Auto-detected if left empty")
        ff_layout.addWidget(ff_lbl)
        ff_layout.addWidget(self.ff_input)
        layout.addLayout(ff_layout)

        # Detect tools button & info
        detect_layout = QHBoxLayout()
        detect_btn = QPushButton("Auto-Detect External Tools")
        detect_btn.clicked.connect(self._detect_tools)
        self.detect_info = QLabel("")
        self.detect_info.setStyleSheet("color: #10B981; font-size: 11px;")
        detect_layout.addWidget(detect_btn)
        detect_layout.addWidget(self.detect_info)
        detect_layout.addStretch()
        layout.addLayout(detect_layout)

        layout.addStretch()

        # Save/Cancel
        btns = QHBoxLayout()
        btns.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet("background-color: #333842;")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("Save Settings")
        save_btn.clicked.connect(self._save)
        btns.addWidget(cancel_btn)
        btns.addWidget(save_btn)
        layout.addLayout(btns)

        self._detect_tools()

    def _browse(self):
        folder = QFileDialog.getExistingDirectory(self, "Default Folder", self.dir_input.text())
        if folder:
            self.dir_input.setText(folder)

    def _detect_tools(self):
        a_bin = find_tool_binary("aria2c", self.aria_input.text())
        ff_bin = find_tool_binary("ffmpeg", self.ff_input.text())
        msgs = []
        if a_bin:
            msgs.append(f"aria2c: Found ({os.path.basename(a_bin)})")
            if not self.aria_input.text():
                self.aria_input.setText(a_bin)
        else:
            msgs.append("aria2c: Not found")

        if ff_bin:
            msgs.append(f"ffmpeg: Found ({os.path.basename(ff_bin)})")
            if not self.ff_input.text():
                self.ff_input.setText(ff_bin)
        else:
            msgs.append("ffmpeg: Not found")

        self.detect_info.setText(" | ".join(msgs))

    def _save(self):
        self.db.set_setting("download_dir", self.dir_input.text())
        self.db.set_setting("max_concurrent", str(self.conc_spin.value()))
        self.db.set_setting("default_connections", str(self.conn_spin.value()))
        self.db.set_setting("max_download_speed", str(self.speed_spin.value()))
        self.db.set_setting("clipboard_monitor", "true" if self.clip_chk.isChecked() else "false")
        self.db.set_setting("smart_routing", "true" if self.smart_route_chk.isChecked() else "false")
        self.db.set_setting("auto_antivirus_scan", "true" if self.defender_chk.isChecked() else "false")
        self.db.set_setting("auto_extract_archives", "true" if self.extract_chk.isChecked() else "false")
        self.db.set_setting("aria2_path", self.aria_input.text())
        self.db.set_setting("ffmpeg_path", self.ff_input.text())
        self.accept()


class ChecksumWorker(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, filepath: str):
        super().__init__()
        self.filepath = filepath

    def run(self):
        try:
            res = calculate_checksums(self.filepath, progress_callback=self.progress.emit)
            self.finished.emit(res)
        except Exception as e:
            self.failed.emit(str(e))


class ChecksumDialog(QDialog):
    def __init__(self, filepath: str, parent=None):
        super().__init__(parent)
        self.filepath = filepath
        self.setWindowTitle("File Integrity Verification - Checksums")
        self.setStyleSheet(DARK_STYLESHEET)
        self.resize(580, 400)
        self.hashes = {}
        self._init_ui()
        self._start_hashing()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        fn = os.path.basename(self.filepath)
        sz = os.path.getsize(self.filepath) if os.path.exists(self.filepath) else 0
        info_lbl = QLabel(f"File: {fn} ({format_file_size(sz)})")
        info_lbl.setStyleSheet("font-size: 13px; font-weight: 600; color: #F1F5F9;")
        layout.addWidget(info_lbl)

        self.pbar = QProgressBar()
        self.pbar.setRange(0, 100)
        self.pbar.setValue(0)
        self.pbar.setTextVisible(True)
        self.pbar.setFormat("Calculating Checksums: %p%")
        self.pbar.setStyleSheet("QProgressBar { background-color: #0F172A; height: 16px; border-radius: 4px; text-align: center; color: white; font-size: 11px; } QProgressBar::chunk { background-color: #2563EB; border-radius: 4px; }")
        layout.addWidget(self.pbar)

        self.md5_input = self._create_hash_row(layout, "MD5:")
        self.sha1_input = self._create_hash_row(layout, "SHA-1:")
        self.sha256_input = self._create_hash_row(layout, "SHA-256:")

        cmp_layout = QVBoxLayout()
        cmp_lbl = QLabel("Compare with Expected Hash:")
        cmp_lbl.setStyleSheet("color: #94A3B8; font-size: 11px; font-weight: 600;")
        cmp_layout.addWidget(cmp_lbl)

        self.cmp_input = QLineEdit()
        self.cmp_input.setPlaceholderText("Paste expected MD5, SHA-1, or SHA-256 checksum here...")
        self.cmp_input.textChanged.connect(self._verify_match)
        cmp_layout.addWidget(self.cmp_input)

        self.match_badge = QLabel("Awaiting input")
        self.match_badge.setStyleSheet("color: #64748B; font-weight: 600; font-size: 12px; padding: 4px;")
        cmp_layout.addWidget(self.match_badge)
        layout.addLayout(cmp_layout)

        layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.setFixedWidth(100)
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)

    def _create_hash_row(self, layout: QVBoxLayout, label_text: str) -> QLineEdit:
        row = QHBoxLayout()
        lbl = QLabel(label_text)
        lbl.setFixedWidth(65)
        lbl.setStyleSheet("color: #CBD5E1; font-weight: 500;")
        inp = QLineEdit()
        inp.setReadOnly(True)
        inp.setPlaceholderText("Calculating...")
        copy_btn = QPushButton("Copy")
        copy_btn.setFixedWidth(60)
        copy_btn.clicked.connect(lambda: QGuiApplication.clipboard().setText(inp.text()))
        row.addWidget(lbl)
        row.addWidget(inp)
        row.addWidget(copy_btn)
        layout.addLayout(row)
        return inp

    def _start_hashing(self):
        self.worker = ChecksumWorker(self.filepath)
        self.worker.progress.connect(self.pbar.setValue)
        self.worker.finished.connect(self._on_hashes_ready)
        self.worker.failed.connect(lambda err: self.match_badge.setText(f"Error: {err}"))
        self.worker.start()

    def _on_hashes_ready(self, res: dict):
        self.hashes = res
        self.pbar.setValue(100)
        self.pbar.setFormat("Hashing Complete")
        self.md5_input.setText(res.get("md5", ""))
        self.sha1_input.setText(res.get("sha1", ""))
        self.sha256_input.setText(res.get("sha256", ""))
        self._verify_match()

    def _verify_match(self):
        exp = self.cmp_input.text().strip().lower()
        if not exp:
            self.match_badge.setText("Awaiting expected hash input")
            self.match_badge.setStyleSheet("color: #64748B; font-weight: 600;")
            return

        if not self.hashes:
            self.match_badge.setText("Calculating checksums...")
            self.match_badge.setStyleSheet("color: #38BDF8; font-weight: 600;")
            return

        all_hashes = [self.hashes.get("md5", ""), self.hashes.get("sha1", ""), self.hashes.get("sha256", "")]
        if exp in all_hashes:
            self.match_badge.setText("VERIFIED MATCH: Checksum perfectly matches file content!")
            self.match_badge.setStyleSheet("color: #10B981; font-weight: bold; font-size: 12px;")
        else:
            self.match_badge.setText("CHECKSUM MISMATCH: Hash does not match MD5, SHA-1, or SHA-256!")
            self.match_badge.setStyleSheet("color: #EF4444; font-weight: bold; font-size: 12px;")


class SiteCrawlerThread(QThread):
    status_msg = pyqtSignal(str, int)
    finished = pyqtSignal(list)
    failed = pyqtSignal(str)

    def __init__(self, start_url: str, depth: int, categories: list, custom_exts: list):
        super().__init__()
        self.start_url = start_url
        self.depth = depth
        self.categories = categories
        self.custom_exts = custom_exts

    def run(self):
        try:
            crawler = SiteGrabberCrawler(
                self.start_url, depth=self.depth,
                categories=self.categories,
                custom_extensions=self.custom_exts
            )
            items = crawler.crawl(progress_callback=lambda msg, count: self.status_msg.emit(msg, count))
            self.finished.emit(items)
        except Exception as e:
            self.failed.emit(str(e))


class SiteGrabberDialog(QDialog):
    def __init__(self, parent=None, db: Optional[Database] = None):
        super().__init__(parent)
        self.db = db or Database()
        self.setWindowTitle("Site Grabber & Link Crawler")
        self.setStyleSheet(DARK_STYLESHEET)
        self.resize(780, 540)
        self.crawler_thread: Optional[SiteCrawlerThread] = None
        self.found_items: List[Dict[str, Any]] = []
        self.added_count = 0
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(18, 18, 18, 18)

        top_layout = QHBoxLayout()
        url_lbl = QLabel("Page URL:")
        url_lbl.setFixedWidth(70)
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://example.com/gallery or web page...")
        top_layout.addWidget(url_lbl)
        top_layout.addWidget(self.url_input)

        depth_lbl = QLabel("Depth:")
        self.depth_spin = QSpinBox()
        self.depth_spin.setRange(1, 3)
        self.depth_spin.setValue(1)
        self.depth_spin.setToolTip("1 = Current page only, 2 = Follow links on same domain")
        top_layout.addWidget(depth_lbl)
        top_layout.addWidget(self.depth_spin)

        self.crawl_btn = QPushButton("Start Crawl")
        self.crawl_btn.clicked.connect(self._toggle_crawl)
        top_layout.addWidget(self.crawl_btn)
        layout.addLayout(top_layout)

        filter_group = QHBoxLayout()
        filter_lbl = QLabel("Capture:")
        filter_lbl.setFixedWidth(70)
        filter_group.addWidget(filter_lbl)

        self.chk_video = QCheckBox("Videos")
        self.chk_video.setChecked(True)
        self.chk_audio = QCheckBox("Audio")
        self.chk_audio.setChecked(True)
        self.chk_docs = QCheckBox("Documents")
        self.chk_docs.setChecked(True)
        self.chk_archives = QCheckBox("Archives")
        self.chk_archives.setChecked(True)
        self.chk_programs = QCheckBox("Programs")
        self.chk_programs.setChecked(True)
        self.chk_images = QCheckBox("Images")
        self.chk_images.setChecked(False)

        filter_group.addWidget(self.chk_video)
        filter_group.addWidget(self.chk_audio)
        filter_group.addWidget(self.chk_docs)
        filter_group.addWidget(self.chk_archives)
        filter_group.addWidget(self.chk_programs)
        filter_group.addWidget(self.chk_images)
        filter_group.addStretch()
        layout.addLayout(filter_group)

        self.status_lbl = QLabel("Enter a URL and click Start Crawl to discover downloadable media and files.")
        self.status_lbl.setStyleSheet("color: #94A3B8; font-size: 11px;")
        layout.addWidget(self.status_lbl)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["", "File Name", "Category", "Ext", "URL"])
        self.table.setColumnWidth(0, 35)
        self.table.setColumnWidth(1, 230)
        self.table.setColumnWidth(2, 95)
        self.table.setColumnWidth(3, 60)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)

        sel_row = QHBoxLayout()
        sel_all = QPushButton("Select All")
        sel_all.clicked.connect(self._select_all)
        desel_all = QPushButton("Deselect All")
        desel_all.clicked.connect(self._deselect_all)
        self.summary_lbl = QLabel("0 files discovered.")
        self.summary_lbl.setStyleSheet("color: #CBD5E1; font-weight: 500;")
        sel_row.addWidget(sel_all)
        sel_row.addWidget(desel_all)
        sel_row.addWidget(self.summary_lbl)
        sel_row.addStretch()
        layout.addLayout(sel_row)

        save_row = QHBoxLayout()
        save_lbl = QLabel("Save To:")
        save_lbl.setFixedWidth(70)
        self.save_input = QLineEdit(self.db.get_setting("download_dir", os.path.expanduser("~/Downloads")))
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self._browse)
        save_row.addWidget(save_lbl)
        save_row.addWidget(self.save_input)
        save_row.addWidget(browse_btn)
        layout.addLayout(save_row)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("Close")
        cancel_btn.setStyleSheet("background-color: #333842;")
        cancel_btn.clicked.connect(self.reject)
        self.import_btn = QPushButton("Add Selected to Queue (0)")
        self.import_btn.setEnabled(False)
        self.import_btn.clicked.connect(self._import_selected)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(self.import_btn)
        layout.addLayout(btn_layout)

    def _browse(self):
        folder = QFileDialog.getExistingDirectory(self, "Save Directory", self.save_input.text())
        if folder:
            self.save_input.setText(folder)

    def _toggle_crawl(self):
        if self.crawler_thread and self.crawler_thread.isRunning():
            self.crawler_thread.terminate()
            self.crawl_btn.setText("Start Crawl")
            self.status_lbl.setText("Crawl cancelled.")
            return

        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Invalid URL", "Please enter a valid target URL.")
            return

        cats = []
        if self.chk_video.isChecked(): cats.append("Video")
        if self.chk_audio.isChecked(): cats.append("Audio")
        if self.chk_docs.isChecked(): cats.append("Documents")
        if self.chk_archives.isChecked(): cats.append("Compressed")
        if self.chk_programs.isChecked(): cats.append("Programs")
        if self.chk_images.isChecked(): cats.append("Images")

        self.table.setRowCount(0)
        self.found_items.clear()
        self.crawl_btn.setText("Stop Crawl")
        self.status_lbl.setText("Connecting and crawling links...")

        self.crawler_thread = SiteCrawlerThread(url, self.depth_spin.value(), cats, [])
        self.crawler_thread.status_msg.connect(lambda msg, count: self.status_lbl.setText(f"{msg} ({count} found)"))
        self.crawler_thread.finished.connect(self._on_crawl_finished)
        self.crawler_thread.failed.connect(self._on_crawl_failed)
        self.crawler_thread.start()

    def _on_crawl_finished(self, items: list):
        self.crawl_btn.setText("Start Crawl")
        self.found_items = items
        self.status_lbl.setText(f"Crawl completed. Discovered {len(items)} downloadable files.")
        self.table.setRowCount(len(items))

        for row, item in enumerate(items):
            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            chk.setCheckState(Qt.CheckState.Checked)

            fn_item = QTableWidgetItem(item["filename"])
            cat_item = QTableWidgetItem(item["category"])
            ext_item = QTableWidgetItem(item["extension"].upper())
            url_item = QTableWidgetItem(item["url"])

            self.table.setItem(row, 0, chk)
            self.table.setItem(row, 1, fn_item)
            self.table.setItem(row, 2, cat_item)
            self.table.setItem(row, 3, ext_item)
            self.table.setItem(row, 4, url_item)

        self._update_counts()

    def _on_crawl_failed(self, err: str):
        self.crawl_btn.setText("Start Crawl")
        self.status_lbl.setText(f"Crawl failed: {err}")

    def _select_all(self):
        for r in range(self.table.rowCount()):
            it = self.table.item(r, 0)
            if it: it.setCheckState(Qt.CheckState.Checked)
        self._update_counts()

    def _deselect_all(self):
        for r in range(self.table.rowCount()):
            it = self.table.item(r, 0)
            if it: it.setCheckState(Qt.CheckState.Unchecked)
        self._update_counts()

    def _update_counts(self):
        cnt = 0
        for r in range(self.table.rowCount()):
            it = self.table.item(r, 0)
            if it and it.checkState() == Qt.CheckState.Checked:
                cnt += 1
        self.summary_lbl.setText(f"{len(self.found_items)} files discovered. {cnt} selected.")
        self.import_btn.setText(f"Add Selected to Queue ({cnt})")
        self.import_btn.setEnabled(cnt > 0)

    def _import_selected(self):
        base_dir = self.save_input.text().strip() or os.path.expanduser("~/Downloads")
        smart_on = self.db.get_setting("smart_routing", "true") == "true"
        self.added_count = 0

        for r in range(self.table.rowCount()):
            it = self.table.item(r, 0)
            if it and it.checkState() == Qt.CheckState.Checked and r < len(self.found_items):
                item = self.found_items[r]
                url = item["url"]
                fn = item["filename"]
                routed_path = compute_smart_save_path(base_dir, fn, smart_on)
                cat = item["category"]
                self.db.add_download(
                    url=url,
                    filename=fn,
                    save_path=routed_path,
                    category=cat,
                    engine_type="auto"
                )
                self.added_count += 1

        self.accept()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Aegis Download Manager")
        self.resize(1080, 640)
        base_dir = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
        icon_path = os.path.join(base_dir, "icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        self.db = Database()
        self.active_workers: Dict[int, Any] = {}
        self._worker_speeds: Dict[int, str] = {}
        self.active_inspector_id: Optional[int] = None
        self.current_filter = "All"
        self._last_clipboard_url = ""

        # Start Named Pipe IPC Server for Browser Extensions
        self.ipc_server = AegisIpcServer(self)
        self.ipc_server.message_received.connect(self._on_browser_ipc_message)
        self.ipc_server.start()

        # Connect Clipboard Monitor
        QGuiApplication.clipboard().dataChanged.connect(self._on_clipboard_changed)

        self._init_ui()
        self._load_downloads()
        self._start_queue_timer()
        self._update_action_states()
        QTimer.singleShot(600, self._process_pending_browser_queue)

        # Periodic check for browser queue to ensure fast response to browser triggers
        self.browser_queue_timer = QTimer(self)
        self.browser_queue_timer.timeout.connect(self._process_pending_browser_queue)
        self.browser_queue_timer.start(1500)

    def closeEvent(self, event):
        if hasattr(self, "browser_queue_timer") and self.browser_queue_timer:
            self.browser_queue_timer.stop()
        if hasattr(self, "queue_timer") and self.queue_timer:
            self.queue_timer.stop()
        if hasattr(self, "ipc_server") and self.ipc_server:
            self.ipc_server.stop()
            self.ipc_server.wait(1000)
        event.accept()

    def _init_ui(self):
        self.setStyleSheet(DARK_STYLESHEET)

        # Toolbar
        toolbar = QToolBar("Main Toolbar")
        toolbar.setIconSize(QSize(18, 18))
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        self.add_act = QAction("New Download", self)
        self.add_act.setToolTip("Add a single download URL")
        self.add_act.triggered.connect(self._open_add_dialog)
        toolbar.addAction(self.add_act)

        self.batch_act = QAction("Batch Import", self)
        self.batch_act.setToolTip("Import multiple URLs from a text file")
        self.batch_act.triggered.connect(self._open_batch_dialog)
        toolbar.addAction(self.batch_act)

        self.grabber_act = QAction("Site Grabber", self)
        self.grabber_act.setToolTip("Crawl web pages to batch download media and files")
        self.grabber_act.triggered.connect(self._open_site_grabber)
        toolbar.addAction(self.grabber_act)

        toolbar.addSeparator()

        self.resume_act = QAction("Resume", self)
        self.resume_act.setToolTip("Resume or start selected download")
        self.resume_act.triggered.connect(self._resume_selected)
        toolbar.addAction(self.resume_act)

        self.pause_act = QAction("Pause", self)
        self.pause_act.setToolTip("Pause selected download")
        self.pause_act.triggered.connect(self._pause_selected)
        toolbar.addAction(self.pause_act)

        self.cancel_act = QAction("Cancel", self)
        self.cancel_act.setToolTip("Cancel selected download")
        self.cancel_act.triggered.connect(self._cancel_selected)
        toolbar.addAction(self.cancel_act)

        toolbar.addSeparator()

        self.open_file_act = QAction("Open File", self)
        self.open_file_act.setToolTip("Open the completed file")
        self.open_file_act.triggered.connect(self._open_selected_file)
        toolbar.addAction(self.open_file_act)

        self.open_folder_act = QAction("Open Folder", self)
        self.open_folder_act.setToolTip("Open destination directory in Explorer")
        self.open_folder_act.triggered.connect(self._open_selected_folder)
        toolbar.addAction(self.open_folder_act)

        self.delete_act = QAction("Delete", self)
        self.delete_act.setToolTip("Remove task from download history")
        self.delete_act.triggered.connect(self._delete_selected)
        toolbar.addAction(self.delete_act)

        toolbar.addSeparator()

        # Clipboard sniffer quick toggle
        self.sniffer_act = QAction("Sniffer", self, checkable=True)
        self.sniffer_act.setToolTip("Toggle automatic clipboard link detection")
        self.sniffer_act.setChecked(self.db.get_setting("clipboard_monitor", "false") == "true")
        self.sniffer_act.toggled.connect(self._toggle_sniffer)
        toolbar.addAction(self.sniffer_act)

        self.settings_act = QAction("Settings", self)
        self.settings_act.setToolTip("Configure speeds, folders, and tools")
        self.settings_act.triggered.connect(self._open_settings)
        toolbar.addAction(self.settings_act)

        self.inspector_act = QAction("Inspector", self, checkable=True)
        self.inspector_act.setToolTip("Toggle macOS download details drawer")
        self.inspector_act.toggled.connect(self._toggle_inspector_action)
        toolbar.addAction(self.inspector_act)

        # Splitter Layout: Sidebar + Table Container
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        # macOS Left Sidebar Container (Navigation + Disk Usage)
        sidebar_container = QWidget()
        sidebar_container.setMinimumWidth(160)
        sidebar_container.setMaximumWidth(360)
        sidebar_container.setStyleSheet("background-color: #1E1E23; border-right: 1px solid rgba(255, 255, 255, 0.08);")
        sidebar_layout = QVBoxLayout(sidebar_container)
        sidebar_layout.setContentsMargins(8, 10, 8, 10)
        sidebar_layout.setSpacing(10)

        # Transfers Section Label
        lbl_transfers = QLabel("TRANSFERS")
        lbl_transfers.setStyleSheet("color: #64748B; font-size: 10px; font-weight: 700; letter-spacing: 0.8px; padding-left: 8px;")
        sidebar_layout.addWidget(lbl_transfers)

        # Sidebar Filter List (Transfers + Categories)
        self.sidebar = QListWidget()
        self.sidebar.setStyleSheet("background-color: transparent; border: none; padding: 0px;")
        self.category_defs = [
            ("All Downloads", "All"),
            ("Downloading", "Downloading"),
            ("Completed", "Completed"),
            ("Paused", "Paused"),
            ("Scheduled", "Scheduled"),
            ("Video", "Video"),
            ("Audio", "Audio"),
            ("Documents", "Documents"),
            ("Compressed", "Compressed"),
            ("Programs", "Programs")
        ]
        for label, cat_key in self.category_defs:
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, cat_key)
            self.sidebar.addItem(item)
        self.sidebar.setCurrentRow(0)
        self.sidebar.currentRowChanged.connect(self._on_category_changed)
        sidebar_layout.addWidget(self.sidebar, stretch=1)

        # macOS Storage Disk Usage Widget at bottom of sidebar
        self.disk_card = QFrame()
        self.disk_card.setStyleSheet("""
            QFrame {
                background-color: rgba(0, 0, 0, 0.35);
                border: 1px solid rgba(255, 255, 255, 0.06);
                border-radius: 10px;
                padding: 4px;
            }
        """)
        disk_vbox = QVBoxLayout(self.disk_card)
        disk_vbox.setContentsMargins(10, 8, 10, 8)
        disk_vbox.setSpacing(6)

        disk_top = QHBoxLayout()
        self.disk_name_lbl = QLabel("Local Storage")
        self.disk_name_lbl.setStyleSheet("color: #E2E8F0; font-size: 11px; font-weight: 600;")
        self.disk_ratio_lbl = QLabel("-- / -- GB")
        self.disk_ratio_lbl.setStyleSheet("color: #94A3B8; font-size: 10px; font-family: monospace;")
        disk_top.addWidget(self.disk_name_lbl)
        disk_top.addStretch()
        disk_top.addWidget(self.disk_ratio_lbl)
        disk_vbox.addLayout(disk_top)

        self.disk_bar = QProgressBar()
        self.disk_bar.setRange(0, 100)
        self.disk_bar.setTextVisible(False)
        self.disk_bar.setStyleSheet("""
            QProgressBar {
                background-color: rgba(255, 255, 255, 0.08);
                border: none;
                border-radius: 3px;
                min-height: 5px;
                max-height: 5px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #007AFF, stop:1 #6366F1);
                border-radius: 3px;
            }
        """)
        disk_vbox.addWidget(self.disk_bar)

        disk_bot = QHBoxLayout()
        self.disk_free_lbl = QLabel("Free: -- GB")
        self.disk_free_lbl.setStyleSheet("color: #64748B; font-size: 10px;")
        self.disk_speed_lbl = QLabel("Speed: Unlimited")
        self.disk_speed_lbl.setStyleSheet("color: #007AFF; font-size: 10px; font-weight: 600;")
        disk_bot.addWidget(self.disk_free_lbl)
        disk_bot.addStretch()
        disk_bot.addWidget(self.disk_speed_lbl)
        disk_vbox.addLayout(disk_bot)

        sidebar_layout.addWidget(self.disk_card)
        splitter.addWidget(sidebar_container)

        # Table Container (Header Bar + Stacked Table/Empty State)
        table_container = QWidget()
        table_vbox = QVBoxLayout(table_container)
        table_vbox.setContentsMargins(12, 10, 12, 10)
        table_vbox.setSpacing(8)

        # Header Bar above table with Title, Count Badge, Quick Multi-Actions, and Search
        hdr_layout = QHBoxLayout()
        self.view_title_lbl = QLabel("All Downloads")
        self.view_title_lbl.setStyleSheet("font-size: 15px; font-weight: 700; color: #F8FAFC;")
        hdr_layout.addWidget(self.view_title_lbl)

        self.count_badge_lbl = QLabel("0 items")
        self.count_badge_lbl.setStyleSheet("""
            QLabel {
                background-color: rgba(255, 255, 255, 0.08);
                color: #94A3B8;
                border: 1px solid rgba(255, 255, 255, 0.06);
                border-radius: 6px;
                padding: 2px 7px;
                font-size: 11px;
                font-family: monospace;
            }
        """)
        hdr_layout.addWidget(self.count_badge_lbl)
        hdr_layout.addSpacing(10)

        # Quick Actions
        self.hdr_start_btn = QPushButton("Start")
        self.hdr_start_btn.setStyleSheet("QPushButton { background-color: rgba(255, 255, 255, 0.08); color: #F1F5F9; border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 7px; padding: 4px 10px; font-size: 11px; } QPushButton:hover { background-color: rgba(255, 255, 255, 0.15); }")
        self.hdr_start_btn.clicked.connect(self._resume_selected)
        hdr_layout.addWidget(self.hdr_start_btn)

        self.hdr_pause_btn = QPushButton("Pause")
        self.hdr_pause_btn.setStyleSheet("QPushButton { background-color: rgba(255, 255, 255, 0.08); color: #F1F5F9; border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 7px; padding: 4px 10px; font-size: 11px; } QPushButton:hover { background-color: rgba(255, 255, 255, 0.15); }")
        self.hdr_pause_btn.clicked.connect(self._pause_selected)
        hdr_layout.addWidget(self.hdr_pause_btn)

        self.hdr_folder_btn = QPushButton("Folder")
        self.hdr_folder_btn.setStyleSheet("QPushButton { background-color: rgba(255, 255, 255, 0.08); color: #F1F5F9; border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 7px; padding: 4px 10px; font-size: 11px; } QPushButton:hover { background-color: rgba(255, 255, 255, 0.15); }")
        self.hdr_folder_btn.clicked.connect(self._open_selected_folder)
        hdr_layout.addWidget(self.hdr_folder_btn)

        hdr_layout.addStretch()

        # Real-time search filter
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter transfers...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setFixedWidth(240)
        self.search_input.textChanged.connect(self._on_search_changed)
        hdr_layout.addWidget(self.search_input)
        table_vbox.addLayout(hdr_layout)

        # Stacked Widget for Table vs Empty State
        self.stack = QStackedWidget()

        # Main Table Widget
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels(["#", "File Name", "Size", "Progress", "Speed", "ETA", "Status", "Date Added"])
        self.table.verticalHeader().setDefaultSectionSize(40)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        self.table.cellDoubleClicked.connect(self._on_double_click)
        self.table.cellClicked.connect(self._on_table_cell_clicked)
        self.table.itemSelectionChanged.connect(self._update_action_states)

        # Header section modes & default widths - Interactive mouse drag resizing and moving
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setSectionsMovable(True)
        header.setCascadingSectionResizes(True)
        header.setHighlightSections(False)

        self.table.setColumnWidth(0, 46)
        self.table.setColumnWidth(1, 260)
        self.table.setColumnWidth(2, 145)
        self.table.setColumnWidth(3, 190)
        self.table.setColumnWidth(4, 95)
        self.table.setColumnWidth(5, 75)
        self.table.setColumnWidth(6, 110)
        self.table.setColumnWidth(7, 130)
        self.stack.addWidget(self.table)

        # Empty State Overlay Widget
        self.empty_widget = QWidget()
        empty_vbox = QVBoxLayout(self.empty_widget)
        empty_vbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_vbox.setSpacing(12)

        self.empty_title = QLabel("No Downloads Found")
        self.empty_title.setStyleSheet("font-size: 16px; font-weight: 600; color: #F1F5F9;")
        self.empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.empty_subtitle = QLabel("No downloads match the current filter. Add a URL to begin.")
        self.empty_subtitle.setStyleSheet("font-size: 12px; color: #94A3B8;")
        self.empty_subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)

        empty_btn = QPushButton("Add Download")
        empty_btn.setFixedWidth(160)
        empty_btn.clicked.connect(self._open_add_dialog)

        empty_vbox.addWidget(self.empty_title)
        empty_vbox.addWidget(self.empty_subtitle)
        empty_vbox.addWidget(empty_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        self.stack.addWidget(self.empty_widget)

        table_vbox.addWidget(self.stack)

        # macOS Summary Metric Bar above Status Bar
        self.summary_footer = QFrame()
        self.summary_footer.setStyleSheet("""
            QFrame {
                background-color: rgba(24, 24, 27, 0.85);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 8px;
                padding: 3px 8px;
            }
        """)
        summary_layout = QHBoxLayout(self.summary_footer)
        summary_layout.setContentsMargins(10, 4, 10, 4)

        self.sum_total_lbl = QLabel("Total: 0 B")
        self.sum_total_lbl.setStyleSheet("color: #94A3B8; font-size: 11px;")
        self.sum_dl_lbl = QLabel("Downloaded: 0 B")
        self.sum_dl_lbl.setStyleSheet("color: #10B981; font-size: 11px; font-weight: 600;")
        self.sum_speed_lbl = QLabel("Speed: 0 KB/s")
        self.sum_speed_lbl.setStyleSheet("color: #007AFF; font-size: 11px; font-weight: 600; font-family: monospace;")
        self.sum_conns_lbl = QLabel("Active Sockets: 0")
        self.sum_conns_lbl.setStyleSheet("color: #A78BFA; font-size: 11px; font-family: monospace;")

        summary_layout.addWidget(self.sum_total_lbl)
        summary_layout.addSpacing(16)
        summary_layout.addWidget(self.sum_dl_lbl)
        summary_layout.addStretch()
        summary_layout.addWidget(self.sum_speed_lbl)
        summary_layout.addSpacing(16)
        summary_layout.addWidget(self.sum_conns_lbl)

        table_vbox.addWidget(self.summary_footer)

        splitter.addWidget(table_container)

        # macOS Right Inspector / Details Panel
        self.inspector_panel = QWidget()
        self.inspector_panel.setMinimumWidth(220)
        self.inspector_panel.setMaximumWidth(460)
        self.inspector_panel.setStyleSheet("""
            QWidget {
                background-color: #1E1E23;
                border-left: 1px solid rgba(255, 255, 255, 0.08);
            }
        """)
        insp_layout = QVBoxLayout(self.inspector_panel)
        insp_layout.setContentsMargins(12, 10, 12, 10)
        insp_layout.setSpacing(10)

        # Header with title and close button
        insp_hdr = QHBoxLayout()
        insp_title = QLabel("Download Details")
        insp_title.setStyleSheet("font-size: 13px; font-weight: 700; color: #F1F5F9; border: none;")
        self.insp_close_btn = QPushButton("✕")
        self.insp_close_btn.setFixedSize(22, 22)
        self.insp_close_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.06);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 11px;
                color: #94A3B8;
                font-size: 10px;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.15);
                color: #FFFFFF;
            }
        """)
        self.insp_close_btn.clicked.connect(self._close_inspector)
        insp_hdr.addWidget(insp_title)
        insp_hdr.addStretch()
        insp_hdr.addWidget(self.insp_close_btn)
        insp_layout.addLayout(insp_hdr)

        # File Card
        file_card = QFrame()
        file_card.setStyleSheet("background-color: rgba(0, 0, 0, 0.35); border: 1px solid rgba(255, 255, 255, 0.06); border-radius: 8px;")
        file_card_vbox = QVBoxLayout(file_card)
        file_card_vbox.setContentsMargins(10, 8, 10, 8)
        file_card_vbox.setSpacing(4)
        self.insp_fn_lbl = QLabel("No Selection")
        self.insp_fn_lbl.setWordWrap(True)
        self.insp_fn_lbl.setStyleSheet("font-size: 12px; font-weight: 600; color: #F8FAFC; border: none;")
        self.insp_cat_lbl = QLabel("CATEGORY: --")
        self.insp_cat_lbl.setStyleSheet("font-size: 10px; font-weight: 700; color: #64748B; border: none; letter-spacing: 0.5px;")
        file_card_vbox.addWidget(self.insp_fn_lbl)
        file_card_vbox.addWidget(self.insp_cat_lbl)
        insp_layout.addWidget(file_card)

        # Transfer Metrics Card
        metrics_hdr = QLabel("TRANSFER METRICS")
        metrics_hdr.setStyleSheet("font-size: 10px; font-weight: 700; color: #64748B; border: none; letter-spacing: 0.6px;")
        insp_layout.addWidget(metrics_hdr)

        metrics_card = QFrame()
        metrics_card.setStyleSheet("background-color: rgba(0, 0, 0, 0.25); border: 1px solid rgba(255, 255, 255, 0.06); border-radius: 8px;")
        m_vbox = QVBoxLayout(metrics_card)
        m_vbox.setContentsMargins(10, 8, 10, 8)
        m_vbox.setSpacing(6)

        def make_metric_row(label_text: str):
            r = QHBoxLayout()
            lbl = QLabel(label_text)
            lbl.setStyleSheet("color: #94A3B8; font-size: 11px; border: none;")
            val = QLabel("--")
            val.setStyleSheet("color: #F1F5F9; font-size: 11px; font-family: monospace; border: none;")
            r.addWidget(lbl)
            r.addStretch()
            r.addWidget(val)
            m_vbox.addLayout(r)
            return val

        self.insp_dl_val = make_metric_row("Downloaded:")
        self.insp_pct_val = make_metric_row("Percentage:")
        self.insp_speed_val = make_metric_row("Current Speed:")
        self.insp_eta_val = make_metric_row("Estimated Time:")
        self.insp_sockets_val = make_metric_row("Sockets / Threads:")
        self.insp_status_val = make_metric_row("Status:")
        insp_layout.addWidget(metrics_card)

        # Source & Location Card
        loc_hdr = QLabel("SOURCE & LOCATION")
        loc_hdr.setStyleSheet("font-size: 10px; font-weight: 700; color: #64748B; border: none; letter-spacing: 0.6px;")
        insp_layout.addWidget(loc_hdr)

        loc_card = QFrame()
        loc_card.setStyleSheet("background-color: rgba(0, 0, 0, 0.25); border: 1px solid rgba(255, 255, 255, 0.06); border-radius: 8px;")
        l_vbox = QVBoxLayout(loc_card)
        l_vbox.setContentsMargins(10, 8, 10, 8)
        l_vbox.setSpacing(6)

        url_lbl = QLabel("URL:")
        url_lbl.setStyleSheet("color: #64748B; font-size: 10px; font-weight: 600; border: none;")
        self.insp_url_edit = QLineEdit()
        self.insp_url_edit.setReadOnly(True)
        self.insp_url_edit.setStyleSheet("background-color: rgba(0, 0, 0, 0.4); border: 1px solid rgba(255, 255, 255, 0.06); border-radius: 6px; color: #38BDF8; font-size: 10px; font-family: monospace; padding: 4px;")
        l_vbox.addWidget(url_lbl)
        l_vbox.addWidget(self.insp_url_edit)

        path_lbl = QLabel("Save Path:")
        path_lbl.setStyleSheet("color: #64748B; font-size: 10px; font-weight: 600; border: none;")
        self.insp_path_edit = QLineEdit()
        self.insp_path_edit.setReadOnly(True)
        self.insp_path_edit.setStyleSheet("background-color: rgba(0, 0, 0, 0.4); border: 1px solid rgba(255, 255, 255, 0.06); border-radius: 6px; color: #CBD5E1; font-size: 10px; font-family: monospace; padding: 4px;")
        l_vbox.addWidget(path_lbl)
        l_vbox.addWidget(self.insp_path_edit)
        insp_layout.addWidget(loc_card)

        # Quick Actions inside Inspector
        insp_layout.addStretch()
        self.insp_copy_btn = QPushButton("Copy Download Link")
        self.insp_copy_btn.setStyleSheet("QPushButton { background-color: rgba(255, 255, 255, 0.08); color: #F1F5F9; border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 7px; padding: 6px; font-size: 11px; } QPushButton:hover { background-color: rgba(255, 255, 255, 0.15); }")
        self.insp_copy_btn.clicked.connect(self._copy_selected_url)
        insp_layout.addWidget(self.insp_copy_btn)

        self.insp_finder_btn = QPushButton("Show in Explorer")
        self.insp_finder_btn.setStyleSheet("QPushButton { background-color: rgba(255, 255, 255, 0.08); color: #F1F5F9; border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 7px; padding: 6px; font-size: 11px; } QPushButton:hover { background-color: rgba(255, 255, 255, 0.15); }")
        self.insp_finder_btn.clicked.connect(self._open_selected_folder)
        insp_layout.addWidget(self.insp_finder_btn)

        splitter.addWidget(self.inspector_panel)
        self.inspector_panel.setVisible(False)
        splitter.setSizes([210, 890, 0])
        main_layout.addWidget(splitter)

        # Status Bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self._update_status_bar()

    def _start_queue_timer(self):
        self.queue_timer = QTimer(self)
        self.queue_timer.setInterval(2500)
        self.queue_timer.timeout.connect(self._on_queue_timer_tick)
        self.queue_timer.start()

    def _on_queue_timer_tick(self):
        # 1. Activate scheduled tasks that are due
        due_tasks = self.db.get_due_scheduled_downloads()
        for t in due_tasks:
            self.db.update_status(t["id"], "queued")
        if due_tasks:
            self._load_downloads()

        # 2. Process ready downloads in queue
        self._process_queue()

    def _open_add_dialog(self):
        dlg = AddDownloadDialog(self, self.db)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_task_data()
            save_path = os.path.join(data["save_dir"], data["filename"])
            cat = self.db.categorize_filename(data["filename"])
            
            task_id = self.db.add_download(
                url=data["url"],
                filename=data["filename"],
                save_path=save_path,
                category=cat,
                engine_type=data["engine"],
                format_id=data["format_id"],
                scheduled_time=data.get("scheduled_time", "")
            )
            self._load_downloads()
            if not data.get("scheduled_time"):
                self._start_task(task_id, data["connections"])

    def _open_batch_dialog(self):
        dlg = BatchImportDialog(self, self.db)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._load_downloads()
            self._process_queue()
            self.status_bar.showMessage(f"Batch import added {dlg.added_count} task(s) to queue.", 5000)

    def _open_site_grabber(self):
        dlg = SiteGrabberDialog(self, self.db)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._load_downloads()
            self._process_queue()
            self.status_bar.showMessage(f"Site Grabber added {dlg.added_count} download(s) to queue.", 5000)

    def _toggle_sniffer(self, checked: bool):
        self.db.set_setting("clipboard_monitor", "true" if checked else "false")
        state = "enabled" if checked else "disabled"
        self.status_bar.showMessage(f"Clipboard link sniffer {state}.", 3000)
        self._update_status_bar()

    def _on_clipboard_changed(self):
        if self.db.get_setting("clipboard_monitor", "false") != "true":
            return
        cb_text = QGuiApplication.clipboard().text().strip()
        if not cb_text or cb_text == self._last_clipboard_url or " " in cb_text:
            return

        parsed = urllib.parse.urlparse(cb_text)
        if parsed.scheme in ("http", "https") and bool(parsed.netloc):
            self._last_clipboard_url = cb_text
            reply = QMessageBox.question(
                self,
                "Clipboard Link Detected",
                f"A downloadable link was detected on the clipboard:\n\n{cb_text}\n\nWould you like to open the download dialog?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                dlg = AddDownloadDialog(self, self.db)
                dlg.url_input.setText(cb_text)
                dlg._analyze_url()
                if dlg.exec() == QDialog.DialogCode.Accepted:
                    data = dlg.get_task_data()
                    save_path = os.path.join(data["save_dir"], data["filename"])
                    cat = self.db.categorize_filename(data["filename"])
                    task_id = self.db.add_download(
                        url=data["url"],
                        filename=data["filename"],
                        save_path=save_path,
                        category=cat,
                        engine_type=data["engine"],
                        format_id=data["format_id"],
                        scheduled_time=data.get("scheduled_time", "")
                    )
                    self._load_downloads()
                    if not data.get("scheduled_time"):
                        self._start_task(task_id, data["connections"])

    def _force_bring_to_foreground(self):
        self.show()
        self.raise_()
        self.activateWindow()
        if sys.platform == "win32":
            force_foreground_window(int(self.winId()))

    def _on_browser_ipc_message(self, msg: dict):
        action = msg.get("action", "download")
        if action in ("bring_to_front", "ping"):
            self._force_bring_to_foreground()
            return

        url = msg.get("url", "").strip()
        if not url:
            return

        self._force_bring_to_foreground()

        dlg = AddDownloadDialog(None, self.db)
        dlg.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)
        dlg.url_input.setText(url)
        if msg.get("filename"):
            dlg.filename_input.setText(msg["filename"])
        if msg.get("format_id"):
            dlg.preferred_format_id = msg.get("format_id")
        elif msg.get("audio_only"):
            dlg.preferred_format_id = "audio"

        dlg._analyze_url()
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()
        if sys.platform == "win32":
            force_foreground_window(int(dlg.winId()))

        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_task_data()
            save_path = os.path.join(data["save_dir"], data["filename"])
            cat = self.db.categorize_filename(data["filename"])
            task_id = self.db.add_download(
                url=data["url"],
                filename=data["filename"],
                save_path=save_path,
                category=cat,
                engine_type=data["engine"],
                format_id=data["format_id"],
                scheduled_time=data.get("scheduled_time", "")
            )
            self._load_downloads()
            if not data.get("scheduled_time"):
                self._start_task(task_id, data["connections"])

    def _process_pending_browser_queue(self):
        import json
        app_data = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "AegisDownloadManager")
        queue_file = os.path.join(app_data, "browser_queue.json")
        if os.path.exists(queue_file):
            try:
                with open(queue_file, "r", encoding="utf-8") as f:
                    queue = json.load(f)
                os.remove(queue_file)
                for item in queue:
                    self._on_browser_ipc_message(item)
            except Exception:
                pass

    def _open_settings(self):
        dlg = SettingsDialog(self, self.db)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.sniffer_act.setChecked(self.db.get_setting("clipboard_monitor", "false") == "true")
            self._update_status_bar()

    def _on_category_changed(self, row: int):
        item = self.sidebar.item(row)
        if item:
            self.current_filter = item.data(Qt.ItemDataRole.UserRole) or "All"
            raw_title = item.text().split("(")[0].strip()
            self.view_title_lbl.setText(f"{raw_title} Downloads")
            self._load_downloads()

    def _on_search_changed(self, text: str):
        self._load_downloads()

    def _update_sidebar_counts(self, all_tasks: List[Dict[str, Any]]):
        counts: Dict[str, int] = {k: 0 for _, k in self.category_defs}
        counts["All"] = len(all_tasks)

        for t in all_tasks:
            st = t.get("status", "")
            cat = t.get("category", "")
            if st == "downloading":
                counts["Downloading"] += 1
            elif st == "completed":
                counts["Completed"] += 1
            elif st == "paused":
                counts["Paused"] += 1
            elif st == "scheduled":
                counts["Scheduled"] += 1

            if cat in counts:
                counts[cat] += 1

        for i, (base_label, cat_key) in enumerate(self.category_defs):
            item = self.sidebar.item(i)
            if item:
                cnt = counts.get(cat_key, 0)
                item.setText(f"{base_label} ({cnt})")

    def _load_downloads(self):
        all_tasks = self.db.get_all_downloads()
        self._update_sidebar_counts(all_tasks)

        search_kw = self.search_input.text().strip().lower() if hasattr(self, "search_input") else ""
        filtered = []

        for t in all_tasks:
            status = t.get("status", "")
            cat = t.get("category", "")

            # Category filter
            if self.current_filter == "All":
                pass
            elif self.current_filter == "Downloading" and status != "downloading":
                continue
            elif self.current_filter == "Completed" and status != "completed":
                continue
            elif self.current_filter == "Paused" and status != "paused":
                continue
            elif self.current_filter == "Scheduled" and status != "scheduled":
                continue
            elif self.current_filter not in ("All", "Downloading", "Completed", "Paused", "Scheduled") and cat != self.current_filter:
                continue

            # Search keyword filter
            if search_kw:
                fn_match = search_kw in t.get("filename", "").lower()
                url_match = search_kw in t.get("url", "").lower()
                if not (fn_match or url_match):
                    continue

            filtered.append(t)

        # Show empty state or table
        if len(filtered) == 0:
            self.stack.setCurrentWidget(self.empty_widget)
            if search_kw:
                self.empty_title.setText("No Matching Downloads")
                self.empty_subtitle.setText(f"No downloads found matching '{search_kw}'.")
            else:
                self.empty_title.setText(f"No {self.current_filter} Downloads")
                self.empty_subtitle.setText("No downloads currently in this category. Click below to add a link.")
        else:
            self.stack.setCurrentWidget(self.table)

        self.table.setRowCount(len(filtered))
        for row, t in enumerate(filtered):
            task_id = str(t["id"])
            filename = t["filename"]
            status = t.get("status", "queued")
            total_size = t.get("total_size", 0)
            downloaded = t.get("downloaded_size", 0)

            # Col 0: ID
            id_item = QTableWidgetItem(task_id)
            id_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            id_item.setForeground(QColor("#64748B"))
            self.table.setItem(row, 0, id_item)

            # Col 1: Filename
            fn_item = QTableWidgetItem(filename)
            fn_font = QFont("Segoe UI", 9)
            fn_font.setBold(True)
            fn_item.setFont(fn_font)
            fn_item.setToolTip(f"{filename}\nURL: {t.get('url', '')}\nSaved: {t.get('save_path', '')}")
            self.table.setItem(row, 1, fn_item)

            # Col 2: Size (Shows downloaded / total numbers)
            size_str = format_size_pair(downloaded, total_size, status)
            size_item = QTableWidgetItem(size_str)
            size_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            size_item.setForeground(QColor("#CBD5E1"))
            size_item.setToolTip(f"Downloaded: {format_file_size(downloaded)}\nTotal Size: {format_file_size(total_size)}")
            self.table.setItem(row, 2, size_item)

            # Col 3: Progress Bar (Shows percentage + visual download numbers; blank when completed)
            if status == "completed":
                self.table.setCellWidget(row, 3, None)
                blank_item = QTableWidgetItem("")
                blank_item.setFlags(blank_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row, 3, blank_item)
            else:
                pct = (downloaded / total_size * 100) if total_size > 0 else 0
                pbar = QProgressBar()
                pbar.setValue(int(pct))
                pbar.setFormat(format_progress_text(pct, downloaded, total_size, status))
                style_progress_bar(pbar, status)
                pbar.setToolTip(f"Progress: {pct:.1f}%\nDownloaded: {format_file_size(downloaded)} / {format_file_size(total_size)}")
                self.table.setCellWidget(row, 3, pbar)

            # Col 4: Speed
            spd_str = t.get("speed", "") or "--"
            spd_item = QTableWidgetItem(spd_str)
            spd_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            if spd_str not in ("--", "", "0 KB/s") and status == "downloading":
                spd_item.setForeground(QColor("#38BDF8"))
            else:
                spd_item.setForeground(QColor("#64748B"))
            self.table.setItem(row, 4, spd_item)

            # Col 5: ETA
            eta_str = t.get("eta", "") or "--"
            eta_item = QTableWidgetItem(eta_str)
            eta_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            eta_item.setForeground(QColor("#94A3B8"))
            self.table.setItem(row, 5, eta_item)

            # Col 6: Status Badge
            disp_status, status_col = format_status(status)
            st_item = QTableWidgetItem(disp_status)
            st_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            st_item.setForeground(QColor(status_col))
            st_font = QFont("Segoe UI", 9)
            st_font.setBold(True)
            st_item.setFont(st_font)
            self.table.setItem(row, 6, st_item)

            # Col 7: Download Date
            raw_date = t.get("completed_at") if (status == "completed" and t.get("completed_at")) else t.get("created_at", "")
            date_str = format_download_date(raw_date)
            date_item = QTableWidgetItem(date_str)
            date_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            date_item.setForeground(QColor("#94A3B8"))
            date_item.setToolTip(f"Added: {t.get('created_at', '--')}\nCompleted: {t.get('completed_at', '--')}")
            self.table.setItem(row, 7, date_item)

        # Update macOS Count Badge
        if hasattr(self, "count_badge_lbl"):
            self.count_badge_lbl.setText(f"{len(filtered)} items")

        # Update Summary Footer metrics
        if hasattr(self, "sum_total_lbl"):
            total_bytes = sum(t.get("total_size", 0) for t in all_tasks)
            downloaded_bytes = sum(t.get("downloaded_size", 0) for t in all_tasks)
            self.sum_total_lbl.setText(f"Total: {format_file_size(total_bytes)}")
            self.sum_dl_lbl.setText(f"Downloaded: {format_file_size(downloaded_bytes)}")

        self._update_live_metrics()
        self._update_disk_usage()
        self._update_action_states()
        self._update_status_bar()

    def _update_action_states(self):
        t_id = self._get_selected_task_id()
        if not t_id:
            self.resume_act.setEnabled(False)
            self.pause_act.setEnabled(False)
            self.cancel_act.setEnabled(False)
            self.open_file_act.setEnabled(False)
            self.open_folder_act.setEnabled(False)
            self.delete_act.setEnabled(False)
            if hasattr(self, "hdr_start_btn"):
                self.hdr_start_btn.setEnabled(False)
                self.hdr_pause_btn.setEnabled(False)
                self.hdr_folder_btn.setEnabled(False)
            return

        task = self.db.get_download(t_id)
        if not task:
            self.resume_act.setEnabled(False)
            self.pause_act.setEnabled(False)
            self.cancel_act.setEnabled(False)
            self.open_file_act.setEnabled(False)
            self.open_folder_act.setEnabled(False)
            self.delete_act.setEnabled(False)
            if hasattr(self, "hdr_start_btn"):
                self.hdr_start_btn.setEnabled(False)
                self.hdr_pause_btn.setEnabled(False)
                self.hdr_folder_btn.setEnabled(False)
            return

        st = task.get("status", "")
        is_active = (st == "downloading" or t_id in self.active_workers)
        file_path = task.get("save_path", "")
        file_exists = bool(file_path and os.path.exists(file_path))

        can_resume = not is_active and st in ("paused", "cancelled", "failed", "queued", "scheduled")
        self.resume_act.setEnabled(can_resume)
        self.pause_act.setEnabled(is_active)
        self.cancel_act.setEnabled(is_active)
        self.open_file_act.setEnabled(file_exists)
        self.open_folder_act.setEnabled(True)
        self.delete_act.setEnabled(True)
        if hasattr(self, "hdr_start_btn"):
            self.hdr_start_btn.setEnabled(can_resume)
            self.hdr_pause_btn.setEnabled(is_active)
            self.hdr_folder_btn.setEnabled(True)

    def _on_table_cell_clicked(self, row: int, col: int):
        if row >= 0 and self.table.item(row, 0):
            try:
                t_id = int(self.table.item(row, 0).text())
                if self.inspector_panel.isVisible():
                    self._open_inspector(t_id)
            except Exception:
                pass

    def _toggle_inspector_action(self, checked: bool):
        if checked:
            t_id = self._get_selected_task_id()
            if t_id:
                self._open_inspector(t_id)
            else:
                self.inspector_panel.setVisible(True)
        else:
            self._close_inspector()

    def _open_inspector(self, task_id: int):
        task = self.db.get_download(task_id)
        if not task:
            return
        self.active_inspector_id = task_id
        self.insp_fn_lbl.setText(task.get("filename", "--"))
        self.insp_cat_lbl.setText(f"CATEGORY: {task.get('category', 'OTHER').upper()}")

        dl = task.get("downloaded_size", 0)
        tot = task.get("total_size", 0)
        pct = (dl / tot * 100) if tot > 0 else 0
        if task.get("status") == "completed":
            pct = 100.0

        self.insp_dl_val.setText(format_size_pair(dl, tot, task.get("status", "")))
        self.insp_pct_val.setText(f"{pct:.1f}%")
        self.insp_speed_val.setText(task.get("speed") or "--")
        self.insp_eta_val.setText(task.get("eta") or "--")
        self.insp_status_val.setText(task.get("status", "--").capitalize())

        worker = self.active_workers.get(task_id)
        conns = getattr(worker, "connections", 16) if worker else "--"
        self.insp_sockets_val.setText(str(conns))

        file_path, folder_path = self._resolve_task_paths(task)
        self.insp_url_edit.setText(task.get("url", ""))
        self.insp_path_edit.setText(file_path if file_path else task.get("save_path", ""))

        if not self.inspector_panel.isVisible():
            self.inspector_panel.setVisible(True)
        if hasattr(self, "inspector_act") and not self.inspector_act.isChecked():
            self.inspector_act.blockSignals(True)
            self.inspector_act.setChecked(True)
            self.inspector_act.blockSignals(False)

    def _close_inspector(self):
        self.inspector_panel.setVisible(False)
        self.active_inspector_id = None
        if hasattr(self, "inspector_act") and self.inspector_act.isChecked():
            self.inspector_act.blockSignals(True)
            self.inspector_act.setChecked(False)
            self.inspector_act.blockSignals(False)

    def _update_disk_usage(self):
        if not hasattr(self, "disk_ratio_lbl"):
            return
        try:
            download_dir = self.db.get_setting("download_dir", os.path.expanduser("~/Downloads"))
            if not os.path.exists(download_dir):
                download_dir = os.path.expanduser("~")
            disk = shutil.disk_usage(download_dir)
            used_gb = (disk.total - disk.free) / (1024**3)
            total_gb = disk.total / (1024**3)
            free_gb = disk.free / (1024**3)
            pct = int(((disk.total - disk.free) / disk.total) * 100) if disk.total > 0 else 0

            self.disk_ratio_lbl.setText(f"{used_gb:.1f} / {total_gb:.0f} GB")
            self.disk_bar.setValue(pct)
            self.disk_free_lbl.setText(f"Free: {free_gb:.1f} GB")
            spd_lim = self.db.get_setting("max_download_speed", "0")
            self.disk_speed_lbl.setText(f"Speed: {spd_lim} KB/s" if spd_lim != "0" else "Speed: Unlimited")
        except Exception:
            pass

    def _update_live_metrics(self):
        if not hasattr(self, "sum_conns_lbl"):
            return
        total_sockets = sum(getattr(w, "connections", 16) for w in self.active_workers.values())
        self.sum_conns_lbl.setText(f"Active Sockets: {total_sockets}")

        if self._worker_speeds:
            speeds = list(self._worker_speeds.values())
            self.sum_speed_lbl.setText(f"Speed: {speeds[0]}")
        else:
            self.sum_speed_lbl.setText("Speed: 0 KB/s")

    def _start_task(self, task_id: int, connections: int = 16):
        task = self.db.get_download(task_id)
        if not task:
            return

        tools_conf = {
            "aria2_path": self.db.get_setting("aria2_path", ""),
            "ffmpeg_path": self.db.get_setting("ffmpeg_path", "")
        }

        save_dir = os.path.dirname(task["save_path"])
        engine = task.get("engine_type", "auto")
        max_speed = int(self.db.get_setting("max_download_speed", "0"))

        # Choose worker: prefer ytdlp for any video stream URL or ytdlp engine
        is_stream = is_media_stream_url(task["url"])
        if engine == "ytdlp" or is_stream:
            worker = YtDlpWorker(task_id, task["url"], task["filename"], save_dir, connections, task.get("format_id", ""), tools_conf, max_speed_kbs=max_speed)
        elif (engine in ("aria2", "auto")) and find_tool_binary("aria2c", tools_conf["aria2_path"]):
            worker = Aria2Worker(task_id, task["url"], task["filename"], save_dir, connections, task.get("format_id", ""), tools_conf, max_speed_kbs=max_speed)
        else:
            # Fallback to direct HTTP with rate limiter and auto-resume
            worker = DirectHttpWorker(task_id, task["url"], task["filename"], save_dir, connections, task.get("format_id", ""), tools_conf, max_speed_kbs=max_speed)

        worker.progress_signal.connect(self._on_worker_progress)
        worker.status_signal.connect(self._on_worker_status)
        worker.finished_signal.connect(self._on_worker_finished)

        self.active_workers[task_id] = worker
        self.db.update_status(task_id, "downloading")
        worker.start()
        self._load_downloads()

    def _on_worker_progress(self, task_id: int, dl: int, tot: int, spd: str, eta: str, pct: float):
        self.db.update_progress(task_id, dl, tot, spd, eta)
        self._worker_speeds[task_id] = spd
        self._update_live_metrics()

        # Update inspector if active for this task
        if self.active_inspector_id == task_id and self.inspector_panel.isVisible():
            self.insp_dl_val.setText(format_size_pair(dl, tot, "downloading"))
            self.insp_pct_val.setText(f"{pct:.1f}%")
            self.insp_speed_val.setText(spd)
            self.insp_eta_val.setText(eta)
            self.insp_status_val.setText("Downloading")

        # Update row if visible
        for row in range(self.table.rowCount()):
            if self.table.item(row, 0) and self.table.item(row, 0).text() == str(task_id):
                # Update Size column with live downloaded / total visual
                if self.table.item(row, 2):
                    self.table.item(row, 2).setText(format_size_pair(dl, tot, "downloading"))
                    self.table.item(row, 2).setToolTip(f"Downloaded: {format_file_size(dl)}\nTotal Size: {format_file_size(tot)}")
                # Update progress bar with live percentage and numbers
                widget = self.table.cellWidget(row, 3)
                if isinstance(widget, QProgressBar):
                    widget.setValue(int(pct))
                    widget.setFormat(format_progress_text(pct, dl, tot, "downloading"))
                    widget.setToolTip(f"Progress: {pct:.1f}%\nDownloaded: {format_file_size(dl)} / {format_file_size(tot)}")
                # Update speed
                if self.table.item(row, 4):
                    self.table.item(row, 4).setText(spd)
                    self.table.item(row, 4).setForeground(QColor("#38BDF8"))
                # Update ETA
                if self.table.item(row, 5):
                    self.table.item(row, 5).setText(eta)
                break

    def _on_worker_status(self, task_id: int, status: str, err: str):
        self.db.update_status(task_id, status, err)
        if status in ("completed", "failed", "cancelled", "paused"):
            self._worker_speeds.pop(task_id, None)
            if task_id in self.active_workers:
                del self.active_workers[task_id]
        self._update_live_metrics()
        self._load_downloads()
        self._check_all_finished()

    def _on_worker_finished(self, task_id: int, file_path: str):
        if file_path:
            norm_fp = os.path.normpath(os.path.abspath(file_path))
            self.db.update_file_path(task_id, norm_fp, os.path.basename(norm_fp))
        self.db.update_status(task_id, "completed")
        self._worker_speeds.pop(task_id, None)
        if task_id in self.active_workers:
            del self.active_workers[task_id]
        self._update_live_metrics()
        self._load_downloads()
        fn = os.path.basename(file_path) if file_path else "file"
        self.status_bar.showMessage(f"Download Finished: {fn}", 5000)
        self._check_all_finished()

        # Post-download automation hooks
        if file_path and os.path.exists(file_path):
            if self.db.get_setting("auto_antivirus_scan", "false") == "true":
                threading.Thread(target=self._run_bg_defender_scan, args=(file_path,), daemon=True).start()
            if self.db.get_setting("auto_extract_archives", "false") == "true" and is_extractable_archive(file_path):
                threading.Thread(target=self._run_bg_archive_extract, args=(file_path,), daemon=True).start()

    def _run_bg_defender_scan(self, file_path: str):
        clean, msg = run_windows_defender_scan(file_path)
        fn = os.path.basename(file_path)
        if clean:
            self.status_bar.showMessage(f"Defender Scan Passed: {fn}", 5000)
        else:
            self.status_bar.showMessage(f"Defender Warning: {fn} - {msg}", 8000)

    def _run_bg_archive_extract(self, file_path: str):
        ok, msg = extract_archive_safe(file_path)
        fn = os.path.basename(file_path)
        if ok:
            self.status_bar.showMessage(f"Archive Extracted: {fn}", 5000)
        else:
            self.status_bar.showMessage(f"Extraction Error: {fn} - {msg}", 6000)

    def _check_all_finished(self):
        if len(self.active_workers) == 0:
            all_dl = self.db.get_all_downloads()
            queued = any(t.get("status") == "queued" for t in all_dl)
            if not queued:
                allow_sleep()

    def _process_queue(self):
        max_conc = int(self.db.get_setting("max_concurrent", "3"))
        if len(self.active_workers) >= max_conc:
            return

        queued_tasks = self.db.get_ordered_queued_downloads()
        for t in queued_tasks:
            if t["id"] not in self.active_workers:
                self._start_task(t["id"])
                if len(self.active_workers) >= max_conc:
                    break

    def _get_selected_task_id(self) -> Optional[int]:
        row = self.table.currentRow()
        if row >= 0 and self.table.item(row, 0):
            try:
                return int(self.table.item(row, 0).text())
            except ValueError:
                return None
        return None

    def _resume_selected(self):
        t_id = self._get_selected_task_id()
        if t_id and t_id not in self.active_workers:
            self._start_task(t_id)

    def _pause_selected(self):
        t_id = self._get_selected_task_id()
        if t_id and t_id in self.active_workers:
            self.active_workers[t_id].pause()

    def _cancel_selected(self):
        t_id = self._get_selected_task_id()
        if t_id and t_id in self.active_workers:
            self.active_workers[t_id].cancel()

    def _restart_selected(self):
        t_id = self._get_selected_task_id()
        if not t_id:
            return
        if t_id in self.active_workers:
            self.active_workers[t_id].cancel()
        self.db.update_progress(t_id, 0, 0, "", "")
        self.db.update_status(t_id, "queued")
        self._load_downloads()
        self._process_queue()

    def _schedule_selected(self):
        t_id = self._get_selected_task_id()
        if not t_id:
            return
        task = self.db.get_download(t_id)
        if not task:
            return
        dlg = ScheduleDialog(self, task.get("scheduled_time", ""))
        if dlg.exec() == QDialog.DialogCode.Accepted:
            iso_val = dlg.get_scheduled_iso()
            self.db.set_schedule(t_id, iso_val)
            self._load_downloads()

    def _resolve_task_paths(self, task: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
        """
        Locates the actual file on disk and its containing directory.
        Handles:
        1. Exact save_path match.
        2. Format/extension variations (e.g. yt-dlp merging to .mkv, .mp4, .webm).
        3. Smart routing subfolder relocations.
        4. Self-heals the database record with the exact on-disk path.
        Returns: (file_path, folder_path) where file_path is None if not yet on disk.
        """
        if not task:
            return (None, None)

        raw_path = task.get("save_path", "")
        task_id = task.get("id")
        fn = task.get("filename", "")

        # 1. Direct path check
        if raw_path:
            norm = os.path.normpath(os.path.abspath(raw_path))
            if os.path.isfile(norm):
                return (norm, os.path.dirname(norm))
            if os.path.isdir(norm):
                return (None, norm)

        # 2. Determine base search directories
        default_dl = os.path.normpath(os.path.abspath(self.db.get_setting("download_dir", os.path.join(os.path.expanduser("~"), "Downloads"))))
        candidate_dirs = []
        if raw_path:
            parent = os.path.dirname(os.path.normpath(os.path.abspath(raw_path)))
            if os.path.isdir(parent) and parent not in candidate_dirs:
                candidate_dirs.append(parent)

        if os.path.isdir(default_dl) and default_dl not in candidate_dirs:
            candidate_dirs.append(default_dl)

        # Smart routing category subdirectories
        cat = task.get("category", "")
        if os.path.isdir(default_dl):
            if cat and cat != "Other":
                cat_dir = os.path.join(default_dl, cat)
                if os.path.isdir(cat_dir) and cat_dir not in candidate_dirs:
                    candidate_dirs.insert(0, cat_dir)
            for std_cat in ("Video", "Music", "Documents", "Programs", "Compressed", "Archives", "Images"):
                sdir = os.path.join(default_dl, std_cat)
                if os.path.isdir(sdir) and sdir not in candidate_dirs:
                    candidate_dirs.append(sdir)

        # 3. Search candidate directories for exact or base-matching files
        base_name = os.path.splitext(fn)[0] if fn else ""
        for d in candidate_dirs:
            if not os.path.isdir(d):
                continue

            # Exact filename check
            if fn:
                exact_path = os.path.join(d, fn)
                if os.path.isfile(exact_path):
                    if task_id:
                        self.db.update_file_path(task_id, exact_path, fn)
                    return (exact_path, d)

            # Prefix/base-name check (e.g. yt-dlp .mkv, .mp4, audio .mp3)
            if base_name:
                try:
                    for entry in os.listdir(d):
                        cand_file = os.path.join(d, entry)
                        if not os.path.isfile(cand_file):
                            continue
                        if entry.endswith(".part") or entry.endswith(".aria2"):
                            continue
                        c_base, _ = os.path.splitext(entry)
                        if c_base == base_name or entry.startswith(base_name):
                            if task_id:
                                self.db.update_file_path(task_id, cand_file, entry)
                            return (cand_file, d)
                except Exception:
                    pass

        # 4. Fallback folder
        fallback_folder = candidate_dirs[0] if candidate_dirs else default_dl
        return (None, fallback_folder if os.path.isdir(fallback_folder) else None)

    def _open_selected_file(self):
        t_id = self._get_selected_task_id()
        if not t_id:
            return
        task = self.db.get_download(t_id)
        if not task:
            return
        file_path, folder_path = self._resolve_task_paths(task)
        if file_path and os.path.isfile(file_path):
            try:
                os.startfile(os.path.normpath(os.path.abspath(file_path)))
            except Exception as e:
                QMessageBox.warning(self, "Open File Failed", f"Could not open file:\n{e}")
        else:
            st = task.get("status", "")
            if st in ("downloading", "queued", "paused", "scheduled"):
                QMessageBox.information(self, "Download Incomplete", f"This task is currently '{st}'. The file is not fully downloaded yet.")
            else:
                QMessageBox.warning(self, "File Not Found", "The downloaded file could not be found on disk.")

    def _open_selected_folder(self):
        t_id = self._get_selected_task_id()
        if not t_id:
            return
        task = self.db.get_download(t_id)
        if not task:
            return
        file_path, folder_path = self._resolve_task_paths(task)
        if file_path and os.path.isfile(file_path):
            norm_file = os.path.normpath(os.path.abspath(file_path))
            try:
                subprocess.Popen(f'explorer.exe /select,"{norm_file}"')
            except Exception:
                os.startfile(os.path.dirname(norm_file))
        elif folder_path and os.path.isdir(folder_path):
            os.startfile(os.path.normpath(os.path.abspath(folder_path)))
        else:
            QMessageBox.warning(self, "Folder Not Found", "Could not locate the download directory on disk.")

    def _copy_selected_url(self):
        t_id = self._get_selected_task_id()
        if not t_id:
            return
        task = self.db.get_download(t_id)
        if task and task.get("url"):
            QGuiApplication.clipboard().setText(task["url"])
            self.status_bar.showMessage("Download link copied to clipboard.", 3000)

    def _delete_selected(self):
        t_id = self._get_selected_task_id()
        if not t_id:
            return
        ans = QMessageBox.question(
            self, "Confirm Delete", 
            "Delete this download task from history?\n(The file on disk will be preserved)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if ans == QMessageBox.StandardButton.Yes:
            if t_id in self.active_workers:
                self.active_workers[t_id].cancel()
            self.db.delete_download(t_id, delete_file=False)
            self._load_downloads()

    def _delete_selected_with_file(self):
        t_id = self._get_selected_task_id()
        if not t_id:
            return
        ans = QMessageBox.question(
            self, "Confirm Permanent Delete", 
            "Are you sure you want to delete this task AND permanently delete the file from your computer?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if ans == QMessageBox.StandardButton.Yes:
            if t_id in self.active_workers:
                self.active_workers[t_id].cancel()
            self.db.delete_download(t_id, delete_file=True)
            self._load_downloads()

    def _on_double_click(self, row: int, col: int):
        id_item = self.table.item(row, 0)
        if not id_item:
            return
        try:
            t_id = int(id_item.text())
        except ValueError:
            return
        task = self.db.get_download(t_id)
        if not task:
            return

        file_path, folder_path = self._resolve_task_paths(task)
        if file_path and os.path.isfile(file_path):
            try:
                os.startfile(os.path.normpath(os.path.abspath(file_path)))
            except Exception as e:
                QMessageBox.warning(self, "Open File Failed", f"Could not open file:\n{e}")
        else:
            st = task.get("status", "")
            if st in ("downloading", "queued", "paused"):
                if folder_path and os.path.isdir(folder_path):
                    os.startfile(os.path.normpath(os.path.abspath(folder_path)))
            else:
                QMessageBox.information(self, "File Not Found", "The downloaded file does not exist on disk yet.")

    def _show_context_menu(self, pos):
        row = self.table.rowAt(pos.y())
        if row < 0:
            return
        self.table.selectRow(row)
        t_id = self._get_selected_task_id()
        if not t_id:
            return
        task = self.db.get_download(t_id)
        if not task:
            return

        st = task.get("status", "")
        is_active = (st == "downloading" or t_id in self.active_workers)
        file_path, folder_path = self._resolve_task_paths(task)
        file_exists = bool(file_path and os.path.isfile(file_path))

        menu = QMenu(self)

        res_act = menu.addAction("Resume / Start")
        res_act.setEnabled(not is_active and st in ("paused", "cancelled", "failed", "queued", "scheduled"))
        res_act.triggered.connect(self._resume_selected)

        pause_act = menu.addAction("Pause")
        pause_act.setEnabled(is_active)
        pause_act.triggered.connect(self._pause_selected)

        cancel_act = menu.addAction("Cancel")
        cancel_act.setEnabled(is_active)
        cancel_act.triggered.connect(self._cancel_selected)

        restart_act = menu.addAction("Restart Download")
        restart_act.triggered.connect(self._restart_selected)

        insp_act = menu.addAction("Inspect Download Details")
        insp_act.triggered.connect(lambda: self._open_inspector(t_id))

        menu.addSeparator()

        sched_act = menu.addAction("Schedule Start Time...")
        sched_act.triggered.connect(self._schedule_selected)

        if st == "queued":
            menu.addSeparator()
            q_top = menu.addAction("Move to Top (Priority)")
            q_top.triggered.connect(lambda: self._move_queue_selected("top"))
            q_up = menu.addAction("Move Up")
            q_up.triggered.connect(lambda: self._move_queue_selected("up"))
            q_down = menu.addAction("Move Down")
            q_down.triggered.connect(lambda: self._move_queue_selected("down"))
            q_bot = menu.addAction("Move to Bottom")
            q_bot.triggered.connect(lambda: self._move_queue_selected("bottom"))

        menu.addSeparator()

        open_f = menu.addAction("Open File")
        open_f.setEnabled(file_exists)
        open_f.triggered.connect(self._open_selected_file)

        open_d = menu.addAction("Open Folder")
        open_d.triggered.connect(self._open_selected_folder)

        if file_exists:
            menu.addSeparator()
            chk_act = menu.addAction("Verify Checksum (MD5 / SHA256)...")
            chk_act.triggered.connect(lambda: self._open_checksum_dialog(file_path))

            av_act = menu.addAction("Scan with Windows Defender")
            av_act.triggered.connect(lambda: self._scan_defender_selected(file_path))

            if is_extractable_archive(file_path):
                ext_act = menu.addAction("Extract Archive Here...")
                ext_act.triggered.connect(lambda: self._extract_archive_selected(file_path))

        copy_u = menu.addAction("Copy Download Link")
        copy_u.triggered.connect(self._copy_selected_url)

        menu.addSeparator()

        del_task = menu.addAction("Delete Task from History")
        del_task.triggered.connect(self._delete_selected)

        del_both = menu.addAction("Delete Task and File from Disk")
        del_both.triggered.connect(self._delete_selected_with_file)

        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _move_queue_selected(self, direction: str):
        t_id = self._get_selected_task_id()
        if t_id and self.db.move_queue(t_id, direction):
            self._load_downloads()
            self.status_bar.showMessage(f"Reordered task #{t_id} {direction} in queue.", 2500)

    def _open_checksum_dialog(self, file_path: str):
        dlg = ChecksumDialog(file_path, self)
        dlg.exec()

    def _scan_defender_selected(self, file_path: str):
        self.status_bar.showMessage(f"Running Defender scan on {os.path.basename(file_path)}...", 3000)
        def _scan():
            clean, msg = run_windows_defender_scan(file_path)
            fn = os.path.basename(file_path)
            if clean:
                self.status_bar.showMessage(f"Defender Clean: {fn} - {msg}", 6000)
            else:
                self.status_bar.showMessage(f"Defender ALERT: {fn} - {msg}", 8000)
        threading.Thread(target=_scan, daemon=True).start()

    def _extract_archive_selected(self, file_path: str):
        self.status_bar.showMessage(f"Extracting {os.path.basename(file_path)}...", 3000)
        def _extract():
            ok, msg = extract_archive_safe(file_path)
            self.status_bar.showMessage(msg, 6000)
        threading.Thread(target=_extract, daemon=True).start()

    def _update_status_bar(self):
        active_count = len(self.active_workers)
        total_count = len(self.db.get_all_downloads())
        spd_lim = self.db.get_setting("max_download_speed", "0")
        spd_display = f"{spd_lim} KB/s" if spd_lim != "0" else "Unlimited"
        clip_status = "Active" if self.db.get_setting("clipboard_monitor", "false") == "true" else "Off"
        self.status_bar.showMessage(
            f"Active Tasks: {active_count} | Registered: {total_count} | Speed Limit: {spd_display} | Sniffer: {clip_status}"
        )
