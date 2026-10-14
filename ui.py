"""
Aegis Download Manager - Modern PyQt6 User Interface
Dark mode, responsive table, category filter, and zero licensing popups.
"""

import os
import sys
import subprocess
import urllib.parse
from typing import Dict, Any, List, Optional
from datetime import datetime
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTableWidget, QTableWidgetItem, QHeaderView, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QLineEdit, QFileDialog, QDialog, QComboBox,
    QSpinBox, QProgressBar, QMessageBox, QMenu, QToolBar, QStatusBar,
    QCheckBox, QDateTimeEdit, QTextEdit, QStackedWidget, QFrame
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QTimer, QDateTime
from PyQt6.QtGui import QIcon, QFont, QColor, QAction, QKeySequence, QClipboard, QGuiApplication

from database import Database
from engine import (
    UrlAnalyzerThread, Aria2Worker, YtDlpWorker, DirectHttpWorker,
    find_tool_binary
)
from ipc_server import AegisIpcServer

def get_category_icon(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    if ext in [".mp4", ".mkv", ".avi", ".mov", ".wmv", ".webm", ".flv", ".m4v"]:
        return "🎬"
    if ext in [".mp3", ".wav", ".aac", ".flac", ".ogg", ".m4a", ".opus"]:
        return "🎵"
    if ext in [".pdf", ".docx", ".doc", ".xlsx", ".pptx", ".txt", ".epub"]:
        return "📄"
    if ext in [".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".iso"]:
        return "📦"
    if ext in [".exe", ".msi", ".bat", ".apk", ".dmg", ".cmd"]:
        return "⚡"
    return "🌐"

def format_status(status: str) -> tuple[str, str]:
    """Returns (display_text, hex_color)."""
    s = (status or "").lower()
    if s == "completed":
        return "✔ Completed", "#10B981"
    elif s == "downloading":
        return "⬇ Downloading", "#38BDF8"
    elif s == "paused":
        return "⏸ Paused", "#F59E0B"
    elif s == "scheduled":
        return "⏰ Scheduled", "#A78BFA"
    elif s == "queued":
        return "⏳ Queued", "#94A3B8"
    elif s == "failed":
        return "✖ Failed", "#F87171"
    elif s == "cancelled":
        return "⏹ Cancelled", "#64748B"
    return status.capitalize(), "#94A3B8"

def style_progress_bar(pbar: QProgressBar, status: str):
    s = (status or "").lower()
    if s == "completed":
        chunk_color = "#10B981"
    elif s == "downloading":
        chunk_color = "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563EB, stop:1 #38BDF8)"
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
            background-color: #1E2128;
            border: 1px solid #2B2F3A;
            border-radius: 4px;
            text-align: center;
            color: #FFFFFF;
            font-size: 11px;
            font-weight: 600;
            min-height: 18px;
            max-height: 18px;
        }}
        QProgressBar::chunk {{
            background: {chunk_color};
            border-radius: 3px;
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
    font-family: "Segoe UI", -apple-system, Arial, sans-serif;
    font-size: 13px;
}
QMainWindow, QDialog {
    background-color: #121316;
    color: #F1F5F9;
    font-family: "Segoe UI", -apple-system, Arial, sans-serif;
    font-size: 13px;
}
QLabel {
    color: #F1F5F9;
    background-color: transparent;
    font-size: 12px;
}
QCheckBox {
    color: #F1F5F9;
    background-color: transparent;
    spacing: 8px;
    font-size: 12px;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #3F4452;
    border-radius: 4px;
    background-color: #1A1C22;
}
QCheckBox::indicator:hover {
    border: 1px solid #3B82F6;
    background-color: #22252E;
}
QCheckBox::indicator:checked {
    background-color: #2563EB;
    border: 1px solid #3B82F6;
}
QRadioButton {
    color: #F1F5F9;
    background-color: transparent;
    spacing: 8px;
    font-size: 12px;
}
QGroupBox {
    color: #F1F5F9;
    border: 1px solid #2B2F3A;
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 10px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 5px;
    color: #38BDF8;
    font-weight: 600;
}
QToolBar {
    background-color: #18191E;
    border-bottom: 1px solid #262932;
    padding: 6px 10px;
    spacing: 6px;
}
QToolButton {
    background-color: transparent;
    color: #F1F5F9;
    padding: 6px 12px;
    border-radius: 6px;
    font-weight: 500;
    font-size: 12px;
}
QToolButton:hover {
    background-color: #272A34;
    color: #FFFFFF;
}
QToolButton:pressed {
    background-color: #1D4ED8;
    color: #FFFFFF;
}
QToolButton:disabled {
    color: #4B5263;
    background-color: transparent;
}
QListWidget {
    background-color: #16171B;
    border: none;
    border-right: 1px solid #262932;
    color: #94A3B8;
    padding: 8px 6px;
    font-size: 13px;
}
QListWidget::item {
    padding: 9px 12px;
    border-radius: 6px;
    margin: 2px 2px;
    font-weight: 500;
}
QListWidget::item:selected {
    background-color: #2563EB;
    color: #FFFFFF;
    font-weight: 600;
}
QListWidget::item:hover:!selected {
    background-color: #22252D;
    color: #F1F5F9;
}
QTableWidget {
    background-color: #121316;
    alternate-background-color: #16171C;
    border: none;
    gridline-color: #1E2129;
    color: #F1F5F9;
    selection-background-color: #1E3A8A;
    selection-color: #FFFFFF;
    font-size: 12px;
}
QTableWidget::item {
    padding: 4px 8px;
    border-bottom: 1px solid #1B1E26;
}
QTableWidget::item:selected {
    background-color: #1E3A8A;
    color: #FFFFFF;
}
QHeaderView::section {
    background-color: #18191E;
    color: #94A3B8;
    padding: 8px 10px;
    border: none;
    border-bottom: 1px solid #262932;
    border-right: 1px solid #1F222A;
    font-weight: 600;
    font-size: 12px;
}
QLineEdit, QComboBox, QSpinBox, QDateTimeEdit {
    background-color: #1A1C22;
    border: 1px solid #2F333E;
    border-radius: 6px;
    padding: 6px 10px;
    color: #F8FAFC;
    font-size: 12px;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDateTimeEdit:focus {
    border: 1px solid #3B82F6;
    background-color: #20222A;
}
QPushButton {
    background-color: #2563EB;
    color: #FFFFFF;
    border: none;
    border-radius: 6px;
    padding: 7px 16px;
    font-weight: 500;
    font-size: 12px;
}
QPushButton:hover {
    background-color: #1D4ED8;
}
QPushButton:pressed {
    background-color: #1E40AF;
}
QPushButton:disabled {
    background-color: #262830;
    color: #64748B;
}
QMenu {
    background-color: #1E2026;
    border: 1px solid #2E323D;
    border-radius: 6px;
    padding: 4px;
    color: #E2E8F0;
    font-size: 12px;
}
QMenu::item {
    padding: 6px 24px 6px 12px;
    border-radius: 4px;
}
QMenu::item:selected {
    background-color: #2563EB;
    color: #FFFFFF;
}
QMenu::item:disabled {
    color: #555C6E;
}
QMenu::separator {
    height: 1px;
    background-color: #2D313B;
    margin: 4px 6px;
}
QStatusBar {
    background-color: #16171B;
    border-top: 1px solid #262932;
    color: #94A3B8;
    font-size: 12px;
    padding: 3px 8px;
}
QSplitter::handle {
    background-color: #262932;
    width: 1px;
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
        load_btn = QPushButton("📂 Open .txt File...")
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

        self.accept()


class AddDownloadDialog(QDialog):
    def __init__(self, parent=None, db: Optional[Database] = None):
        super().__init__(parent)
        self.db = db or Database()
        self.setWindowTitle("Add New Download")
        self.setStyleSheet(DARK_STYLESHEET)
        self.resize(580, 400)
        self.analyzer_thread: Optional[UrlAnalyzerThread] = None
        self.analyzed_result: Dict[str, Any] = {}
        self._init_ui()
        self._check_clipboard()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # URL Input
        url_layout = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Paste download link (HTTP, HTTPS, YouTube, direct file...)")
        self.analyze_btn = QPushButton("Analyze Link")
        self.analyze_btn.clicked.connect(self._analyze_url)
        url_layout.addWidget(self.url_input)
        url_layout.addWidget(self.analyze_btn)
        layout.addLayout(url_layout)

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
        cb = QGuiApplication.clipboard().text().strip()
        if cb.startswith("http://") or cb.startswith("https://"):
            self.url_input.setText(cb)

    def _browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Download Folder", self.save_input.text())
        if folder:
            self.save_input.setText(folder)

    def _analyze_url(self):
        url = self.url_input.text().strip()
        if not url:
            return

        self.analyze_btn.setEnabled(False)
        self.analyze_btn.setText("Probing...")
        self.status_lbl.setText("Analyzing target URL and extracting stream metadata...")

        tools = {
            "aria2_path": self.db.get_setting("aria2_path", ""),
            "ffmpeg_path": self.db.get_setting("ffmpeg_path", "")
        }
        self.analyzer_thread = UrlAnalyzerThread(url, tools)
        self.analyzer_thread.analysis_complete.connect(self._on_analysis_done)
        self.analyzer_thread.analysis_failed.connect(self._on_analysis_fail)
        self.analyzer_thread.start()

    def _on_analysis_done(self, result: Dict[str, Any]):
        self.analyzed_result = result
        self.analyze_btn.setEnabled(True)
        self.analyze_btn.setText("Analyze Link")
        self.filename_input.setText(result.get("filename", "download"))

        formats = result.get("formats", [])
        if formats:
            self.format_combo.clear()
            for f in formats:
                self.format_combo.addItem(f["label"], f["id"])
            self.format_combo.setEnabled(True)
            self.status_lbl.setText(f"Media stream detected! Found {len(formats)} quality formats.")
        else:
            self.format_combo.clear()
            self.format_combo.setEnabled(False)
            size = result.get("filesize", 0)
            if size > 0:
                mb = size / (1024 * 1024)
                self.status_lbl.setText(f"Direct download verified. Size: {mb:.2f} MB")
            else:
                self.status_lbl.setText("Direct download link verified.")

    def _on_analysis_fail(self, err: str):
        self.analyze_btn.setEnabled(True)
        self.analyze_btn.setText("Analyze Link")
        self.status_lbl.setText(f"Analysis note: {err} (Direct download will proceed)")

    def _accept_download(self):
        url = self.url_input.text().strip()
        filename = self.filename_input.text().strip()
        save_dir = self.save_input.text().strip()

        if not url:
            QMessageBox.warning(self, "Invalid Input", "Please provide a download URL.")
            return
        if not filename:
            filename = "download.bin"
        if not save_dir:
            save_dir = os.path.expanduser("~/Downloads")

        self.accept()

    def get_task_data(self) -> Dict[str, Any]:
        fmt_id = self.format_combo.currentData() if self.format_combo.isEnabled() else ""
        engine = self.analyzed_result.get("engine", "auto")
        scheduled_iso = self.schedule_dt.dateTime().toString(Qt.DateFormat.ISODate) if self.schedule_chk.isChecked() else ""
        return {
            "url": self.url_input.text().strip(),
            "filename": self.filename_input.text().strip() or "download.bin",
            "save_dir": self.save_input.text().strip(),
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
        self.db.set_setting("aria2_path", self.aria_input.text())
        self.db.set_setting("ffmpeg_path", self.ff_input.text())
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

    def closeEvent(self, event):
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

        self.add_act = QAction("➕ New Download", self)
        self.add_act.setToolTip("Add a single download URL")
        self.add_act.triggered.connect(self._open_add_dialog)
        toolbar.addAction(self.add_act)

        self.batch_act = QAction("📑 Batch Import", self)
        self.batch_act.setToolTip("Import multiple URLs from a text file")
        self.batch_act.triggered.connect(self._open_batch_dialog)
        toolbar.addAction(self.batch_act)

        toolbar.addSeparator()

        self.resume_act = QAction("▶ Resume", self)
        self.resume_act.setToolTip("Resume or start selected download")
        self.resume_act.triggered.connect(self._resume_selected)
        toolbar.addAction(self.resume_act)

        self.pause_act = QAction("⏸ Pause", self)
        self.pause_act.setToolTip("Pause selected download")
        self.pause_act.triggered.connect(self._pause_selected)
        toolbar.addAction(self.pause_act)

        self.cancel_act = QAction("⏹ Cancel", self)
        self.cancel_act.setToolTip("Cancel selected download")
        self.cancel_act.triggered.connect(self._cancel_selected)
        toolbar.addAction(self.cancel_act)

        toolbar.addSeparator()

        self.open_file_act = QAction("📄 Open File", self)
        self.open_file_act.setToolTip("Open the completed file")
        self.open_file_act.triggered.connect(self._open_selected_file)
        toolbar.addAction(self.open_file_act)

        self.open_folder_act = QAction("📁 Open Folder", self)
        self.open_folder_act.setToolTip("Open destination directory in Explorer")
        self.open_folder_act.triggered.connect(self._open_selected_folder)
        toolbar.addAction(self.open_folder_act)

        self.delete_act = QAction("🗑 Delete", self)
        self.delete_act.setToolTip("Remove task from download history")
        self.delete_act.triggered.connect(self._delete_selected)
        toolbar.addAction(self.delete_act)

        toolbar.addSeparator()

        # Clipboard sniffer quick toggle
        self.sniffer_act = QAction("📋 Sniffer", self, checkable=True)
        self.sniffer_act.setToolTip("Toggle automatic clipboard link detection")
        self.sniffer_act.setChecked(self.db.get_setting("clipboard_monitor", "false") == "true")
        self.sniffer_act.toggled.connect(self._toggle_sniffer)
        toolbar.addAction(self.sniffer_act)

        self.settings_act = QAction("⚙ Settings", self)
        self.settings_act.setToolTip("Configure speeds, folders, and tools")
        self.settings_act.triggered.connect(self._open_settings)
        toolbar.addAction(self.settings_act)

        # Splitter Layout: Sidebar + Table Container
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Sidebar Filter List
        self.sidebar = QListWidget()
        self.sidebar.setFixedWidth(195)
        self.category_defs = [
            ("📂 All", "All"),
            ("⬇ Downloading", "Downloading"),
            ("✔ Completed", "Completed"),
            ("⏸ Paused", "Paused"),
            ("⏰ Scheduled", "Scheduled"),
            ("🎬 Video", "Video"),
            ("🎵 Audio", "Audio"),
            ("📄 Documents", "Documents"),
            ("📦 Compressed", "Compressed"),
            ("⚡ Programs", "Programs")
        ]
        for label, cat_key in self.category_defs:
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, cat_key)
            self.sidebar.addItem(item)
        self.sidebar.setCurrentRow(0)
        self.sidebar.currentRowChanged.connect(self._on_category_changed)
        splitter.addWidget(self.sidebar)

        # Table Container (Header Bar + Stacked Table/Empty State)
        table_container = QWidget()
        table_vbox = QVBoxLayout(table_container)
        table_vbox.setContentsMargins(12, 10, 12, 10)
        table_vbox.setSpacing(8)

        # Header Bar above table
        hdr_layout = QHBoxLayout()
        self.view_title_lbl = QLabel("All Downloads")
        self.view_title_lbl.setStyleSheet("font-size: 15px; font-weight: 600; color: #F8FAFC;")
        hdr_layout.addWidget(self.view_title_lbl)
        hdr_layout.addStretch()

        # Real-time search filter
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Filter downloads by name or URL...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setFixedWidth(270)
        self.search_input.textChanged.connect(self._on_search_changed)
        hdr_layout.addWidget(self.search_input)
        table_vbox.addLayout(hdr_layout)

        # Stacked Widget for Table vs Empty State
        self.stack = QStackedWidget()

        # Main Table Widget
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels(["#", "File Name", "Size", "Progress", "Speed", "ETA", "Status", "Download Date"])
        self.table.verticalHeader().setDefaultSectionSize(40)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        self.table.cellDoubleClicked.connect(self._on_double_click)
        self.table.itemSelectionChanged.connect(self._update_action_states)

        # Header section modes & default widths
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 46)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(2, 90)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(3, 175)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(4, 95)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(5, 75)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(6, 120)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(7, 135)
        self.stack.addWidget(self.table)

        # Empty State Overlay Widget
        self.empty_widget = QWidget()
        empty_vbox = QVBoxLayout(self.empty_widget)
        empty_vbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_vbox.setSpacing(12)

        empty_icon = QLabel("📥")
        empty_icon.setStyleSheet("font-size: 42px; color: #475569;")
        empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.empty_title = QLabel("No Downloads Found")
        self.empty_title.setStyleSheet("font-size: 16px; font-weight: 600; color: #F1F5F9;")
        self.empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.empty_subtitle = QLabel("No downloads match the current filter. Add a URL to begin.")
        self.empty_subtitle.setStyleSheet("font-size: 12px; color: #94A3B8;")
        self.empty_subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)

        empty_btn = QPushButton("➕ Add Download")
        empty_btn.setFixedWidth(160)
        empty_btn.clicked.connect(self._open_add_dialog)

        empty_vbox.addWidget(empty_icon)
        empty_vbox.addWidget(self.empty_title)
        empty_vbox.addWidget(self.empty_subtitle)
        empty_vbox.addWidget(empty_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        self.stack.addWidget(self.empty_widget)

        table_vbox.addWidget(self.stack)
        splitter.addWidget(table_container)

        splitter.setSizes([195, 885])
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

    def _on_browser_ipc_message(self, msg: dict):
        url = msg.get("url", "").strip()
        if not url:
            return

        self.activateWindow()
        self.raise_()

        # Prompt user confirmation before adding browser download
        reply = QMessageBox.question(
            self,
            "Browser Download Request",
            f"Incoming download request from browser extension:\n\n{url}\n\nAdd this file to Aegis Download Manager?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            dlg = AddDownloadDialog(self, self.db)
            dlg.url_input.setText(url)
            if msg.get("filename"):
                dlg.filename_input.setText(msg["filename"])
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

            # Col 1: Filename with category icon
            icon = get_category_icon(filename)
            fn_item = QTableWidgetItem(f"{icon} {filename}")
            fn_font = QFont("Segoe UI", 9)
            fn_font.setBold(True)
            fn_item.setFont(fn_font)
            fn_item.setToolTip(f"{filename}\nURL: {t.get('url', '')}\nSaved: {t.get('save_path', '')}")
            self.table.setItem(row, 1, fn_item)

            # Col 2: Size
            size_str = f"{total_size / (1024*1024):.2f} MB" if total_size > 0 else "--"
            size_item = QTableWidgetItem(size_str)
            size_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            size_item.setForeground(QColor("#CBD5E1"))
            self.table.setItem(row, 2, size_item)

            # Col 3: Progress Bar
            pct = (downloaded / total_size * 100) if total_size > 0 else 0
            if status == "completed":
                pct = 100.0
            pbar = QProgressBar()
            pbar.setValue(int(pct))
            pbar.setFormat(f"{pct:.1f}%")
            style_progress_bar(pbar, status)
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
            return

        task = self.db.get_download(t_id)
        if not task:
            self.resume_act.setEnabled(False)
            self.pause_act.setEnabled(False)
            self.cancel_act.setEnabled(False)
            self.open_file_act.setEnabled(False)
            self.open_folder_act.setEnabled(False)
            self.delete_act.setEnabled(False)
            return

        st = task.get("status", "")
        is_active = (st == "downloading" or t_id in self.active_workers)
        file_path = task.get("save_path", "")
        file_exists = bool(file_path and os.path.exists(file_path))

        self.resume_act.setEnabled(not is_active and st in ("paused", "cancelled", "failed", "queued", "scheduled"))
        self.pause_act.setEnabled(is_active)
        self.cancel_act.setEnabled(is_active)
        self.open_file_act.setEnabled(file_exists)
        self.open_folder_act.setEnabled(True)
        self.delete_act.setEnabled(True)

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

        # Choose worker
        if engine == "ytdlp":
            worker = YtDlpWorker(task_id, task["url"], task["filename"], save_dir, connections, task.get("format_id", ""), tools_conf, max_speed_kbs=max_speed)
        elif engine == "aria2" and find_tool_binary("aria2c", tools_conf["aria2_path"]):
            worker = Aria2Worker(task_id, task["url"], task["filename"], save_dir, connections, task.get("format_id", ""), tools_conf, max_speed_kbs=max_speed)
        else:
            # Fallback to direct HTTP with rate limiter
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
        # Update row if visible
        for row in range(self.table.rowCount()):
            if self.table.item(row, 0) and self.table.item(row, 0).text() == str(task_id):
                # Update total size display if known
                if tot > 0 and self.table.item(row, 2):
                    self.table.item(row, 2).setText(f"{tot / (1024*1024):.2f} MB")
                # Update progress bar
                widget = self.table.cellWidget(row, 3)
                if isinstance(widget, QProgressBar):
                    widget.setValue(int(pct))
                    widget.setFormat(f"{pct:.1f}%")
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
            if task_id in self.active_workers:
                del self.active_workers[task_id]
        self._load_downloads()

    def _on_worker_finished(self, task_id: int, file_path: str):
        self.db.update_status(task_id, "completed")
        if task_id in self.active_workers:
            del self.active_workers[task_id]
        self._load_downloads()
        self.status_bar.showMessage(f"Download Finished: {os.path.basename(file_path)}", 5000)

    def _process_queue(self):
        max_conc = int(self.db.get_setting("max_concurrent", "3"))
        if len(self.active_workers) >= max_conc:
            return

        all_tasks = self.db.get_all_downloads()
        for t in all_tasks:
            if t["status"] == "queued" and t["id"] not in self.active_workers:
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

    def _open_selected_file(self):
        t_id = self._get_selected_task_id()
        if not t_id:
            return
        task = self.db.get_download(t_id)
        if task:
            path = task.get("save_path", "")
            if path and os.path.exists(path):
                os.startfile(path)
            else:
                QMessageBox.information(self, "File Not Found", "The downloaded file does not exist on disk yet.")

    def _open_selected_folder(self):
        t_id = self._get_selected_task_id()
        if not t_id:
            return
        task = self.db.get_download(t_id)
        if task:
            path = task["save_path"]
            folder = os.path.dirname(path) if os.path.exists(path) else self.db.get_setting("download_dir")
            if os.path.exists(folder):
                os.startfile(folder)

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
        t_id = int(self.table.item(row, 0).text())
        task = self.db.get_download(t_id)
        if task and os.path.exists(task["save_path"]):
            os.startfile(task["save_path"])
        else:
            self._open_selected_folder()

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
        file_path = task.get("save_path", "")
        file_exists = bool(file_path and os.path.exists(file_path))

        menu = QMenu(self)

        res_act = menu.addAction("▶ Resume / Start")
        res_act.setEnabled(not is_active and st in ("paused", "cancelled", "failed", "queued", "scheduled"))
        res_act.triggered.connect(self._resume_selected)

        pause_act = menu.addAction("⏸ Pause")
        pause_act.setEnabled(is_active)
        pause_act.triggered.connect(self._pause_selected)

        cancel_act = menu.addAction("⏹ Cancel")
        cancel_act.setEnabled(is_active)
        cancel_act.triggered.connect(self._cancel_selected)

        restart_act = menu.addAction("🔄 Restart Download")
        restart_act.triggered.connect(self._restart_selected)

        menu.addSeparator()

        sched_act = menu.addAction("⏰ Schedule Start Time...")
        sched_act.triggered.connect(self._schedule_selected)

        menu.addSeparator()

        open_f = menu.addAction("📄 Open File")
        open_f.setEnabled(file_exists)
        open_f.triggered.connect(self._open_selected_file)

        open_d = menu.addAction("📁 Open Folder")
        open_d.triggered.connect(self._open_selected_folder)

        copy_u = menu.addAction("🔗 Copy Download Link")
        copy_u.triggered.connect(self._copy_selected_url)

        menu.addSeparator()

        del_task = menu.addAction("🗑 Delete Task from History")
        del_task.triggered.connect(self._delete_selected)

        del_both = menu.addAction("❌ Delete Task and File from Disk")
        del_both.triggered.connect(self._delete_selected_with_file)

        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _update_status_bar(self):
        active_count = len(self.active_workers)
        total_count = len(self.db.get_all_downloads())
        spd_lim = self.db.get_setting("max_download_speed", "0")
        spd_display = f"{spd_lim} KB/s" if spd_lim != "0" else "Unlimited"
        clip_status = "Active" if self.db.get_setting("clipboard_monitor", "false") == "true" else "Off"
        self.status_bar.showMessage(
            f"Active Tasks: {active_count} | Registered: {total_count} | Speed Limit: {spd_display} | Sniffer: {clip_status}"
        )
