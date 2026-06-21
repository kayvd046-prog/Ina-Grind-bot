from pathlib import Path
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QComboBox, QCheckBox, QLabel,
)
from ievr_bot.config import load_profile
from gui.worker import BotWorker
from gui.widgets import StatusPanel, LogPanel, PreviewPanel

DARK_QSS = """
QWidget { background:#1e1f22; color:#e6e6e6; font-size:13px; }
QGroupBox { border:1px solid #3a3b3f; border-radius:6px; margin-top:10px; }
QGroupBox::title { subcontrol-origin: margin; left:8px; padding:0 4px; }
QPushButton { background:#3a6df0; border:none; padding:8px 14px; border-radius:6px; }
QPushButton:disabled { background:#444; }
QPlainTextEdit { background:#141517; }
"""


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("IEVR Commander Bot")
        self.worker: BotWorker | None = None

        self.profile_box = QComboBox(); self.profile_box.addItems(["pve", "ranked"])
        self.controller_box = QComboBox()
        self.controller_box.addItems(["vgamepad", "keyboard", "null"])
        self.dry_run = QCheckBox("Dry-run (no input)")
        self.start_btn = QPushButton("Start")
        self.stop_btn = QPushButton("Stop"); self.stop_btn.setEnabled(False)

        self.status_panel = StatusPanel()
        self.log_panel = LogPanel()
        self.preview_panel = PreviewPanel()

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Profile:")); controls.addWidget(self.profile_box)
        controls.addWidget(QLabel("Input:")); controls.addWidget(self.controller_box)
        controls.addWidget(self.dry_run)
        controls.addStretch()
        controls.addWidget(self.start_btn); controls.addWidget(self.stop_btn)

        body = QHBoxLayout()
        left = QVBoxLayout(); left.addWidget(self.status_panel); left.addWidget(self.preview_panel)
        body.addLayout(left, 1); body.addWidget(self.log_panel, 1)

        root = QVBoxLayout(); root.addLayout(controls); root.addLayout(body)
        container = QWidget(); container.setLayout(root)
        self.setCentralWidget(container)
        self.setStyleSheet(DARK_QSS)

        self.start_btn.clicked.connect(self.start)
        self.stop_btn.clicked.connect(self.stop)

    def start(self):
        profiles = Path(__file__).resolve().parents[1] / "profiles"
        profile = load_profile(self.profile_box.currentText(), profiles)
        self.worker = BotWorker(
            profile, self.controller_box.currentText(), self.dry_run.isChecked())
        self.worker.status.connect(self._on_status)
        self.worker.log_line.connect(self.log_panel.append)
        self.worker.stopped.connect(self._on_stopped)
        self.worker.start()
        self.start_btn.setEnabled(False); self.stop_btn.setEnabled(True)

    def stop(self):
        if self.worker:
            self.worker.stop()

    def _on_status(self, upd):
        self.status_panel.update_status(upd)
        self.preview_panel.update_frame(upd.frame)

    def _on_stopped(self):
        self.start_btn.setEnabled(True); self.stop_btn.setEnabled(False)
