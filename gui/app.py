from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QComboBox, QCheckBox, QLabel, QFrame, QStackedWidget, QButtonGroup,
    QSizePolicy,
)
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtCore import Qt

from ievr_bot.config import load_profile, available_profiles
from ievr_bot.paths import profiles_dir, assets_dir
from gui.worker import BotWorker
from gui.widgets import LogPanel, PreviewPanel
from gui.theme import QSS, state_color
from gui.template_tab import TemplateTab


class StatCard(QFrame):
    """A dashboard tile: small caption on top, big value below."""

    def __init__(self, title: str, small: bool = False):
        super().__init__()
        self.setObjectName("card")
        self.title = QLabel(title.upper())
        self.title.setObjectName("cardTitle")
        self.value = QLabel("—")
        self.value.setObjectName("cardSmall" if small else "cardValue")
        self.value.setWordWrap(small)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.addWidget(self.title)
        lay.addWidget(self.value)
        lay.addStretch()

    def set_value(self, text: str, color: str | None = None):
        self.value.setText(text)
        if color:
            self.value.setStyleSheet(
                f"color: {color}; background: transparent;")


class RunPage(QWidget):
    """Controls bar, status cards, live preview and log."""

    def __init__(self):
        super().__init__()
        profiles = available_profiles(profiles_dir()) or ["pve", "ranked"]
        self.profile_box = QComboBox(); self.profile_box.addItems(profiles)
        self.controller_box = QComboBox()
        self.controller_box.addItems(["vgamepad", "keyboard", "null"])
        self.dry_run = QCheckBox("Dry-run (no input)")
        self.start_btn = QPushButton("▶  Start"); self.start_btn.setObjectName("start")
        self.stop_btn = QPushButton("■  Stop"); self.stop_btn.setObjectName("stop")
        self.stop_btn.setEnabled(False)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Profile:")); controls.addWidget(self.profile_box)
        controls.addSpacing(8)
        controls.addWidget(QLabel("Input:")); controls.addWidget(self.controller_box)
        controls.addSpacing(8)
        controls.addWidget(self.dry_run)
        controls.addStretch()
        controls.addWidget(self.start_btn); controls.addWidget(self.stop_btn)

        self.state_card = StatCard("State")
        self.matches_card = StatCard("Matches")
        self.matches_card.set_value("0")
        self.action_card = StatCard("Action", small=True)
        cards = QHBoxLayout()
        for c in (self.state_card, self.matches_card, self.action_card):
            c.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            c.setMinimumHeight(92)
            cards.addWidget(c, 1)

        self.preview_panel = PreviewPanel()
        self.log_panel = LogPanel()
        body = QHBoxLayout()
        body.addWidget(self.preview_panel, 1)
        body.addWidget(self.log_panel, 1)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(14)
        root.addLayout(controls)
        root.addLayout(cards)
        root.addLayout(body, 1)

    def update_status(self, upd):
        self.state_card.set_value(upd.state.name, state_color(upd.state))
        self.matches_card.set_value(str(upd.matches))
        self.action_card.set_value(f"{upd.action}\nscore {upd.score:.2f}")
        self.preview_panel.update_frame(upd.frame)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("IEVR Commander Bot")
        self.resize(1024, 640)
        icon_path = assets_dir() / "icon.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self.worker: BotWorker | None = None

        # --- sidebar ---
        logo = QLabel()
        logo_path = assets_dir() / "logo.png"
        if logo_path.exists():
            logo.setPixmap(QPixmap(str(logo_path)).scaled(
                56, 56, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        logo.setAlignment(Qt.AlignCenter)
        title = QLabel("IEVR"); title.setObjectName("appTitle")
        title.setAlignment(Qt.AlignCenter)
        subtitle = QLabel("Commander Bot"); subtitle.setObjectName("appSub")
        subtitle.setAlignment(Qt.AlignCenter)

        self.nav_run = QPushButton("  Run"); self.nav_templates = QPushButton("  Templates")
        nav_group = QButtonGroup(self)
        for i, b in enumerate((self.nav_run, self.nav_templates)):
            b.setObjectName("nav"); b.setCheckable(True)
            nav_group.addButton(b, i)
        self.nav_run.setChecked(True)

        side = QVBoxLayout()
        side.setContentsMargins(14, 20, 14, 14)
        side.setSpacing(6)
        side.addWidget(logo); side.addWidget(title); side.addWidget(subtitle)
        side.addSpacing(22)
        side.addWidget(self.nav_run); side.addWidget(self.nav_templates)
        side.addStretch()
        sidebar = QWidget(); sidebar.setObjectName("sidebar")
        sidebar.setLayout(side); sidebar.setFixedWidth(168)

        # --- pages ---
        self.run_page = RunPage()
        self.template_tab = TemplateTab()
        self.template_tab.log_line.connect(self.run_page.log_panel.append)
        self.stack = QStackedWidget()
        self.stack.addWidget(self.run_page)
        self.stack.addWidget(self.template_tab)
        nav_group.idClicked.connect(self.stack.setCurrentIndex)

        root = QHBoxLayout()
        root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)
        root.addWidget(sidebar); root.addWidget(self.stack, 1)
        container = QWidget(); container.setLayout(root)
        self.setCentralWidget(container)
        self.setStyleSheet(QSS)

        self.run_page.start_btn.clicked.connect(self.start)
        self.run_page.stop_btn.clicked.connect(self.stop)

    def start(self):
        rp = self.run_page
        profile = load_profile(rp.profile_box.currentText(), profiles_dir())
        self.worker = BotWorker(
            profile, rp.controller_box.currentText(), rp.dry_run.isChecked())
        self.worker.status.connect(self._on_status)
        self.worker.log_line.connect(rp.log_panel.append)
        self.worker.stopped.connect(self._on_stopped)
        self.worker.start()
        rp.start_btn.setEnabled(False); rp.stop_btn.setEnabled(True)

    def stop(self):
        if self.worker:
            self.worker.stop()

    def _on_status(self, upd):
        self.run_page.update_status(upd)

    def _on_stopped(self):
        self.run_page.start_btn.setEnabled(True)
        self.run_page.stop_btn.setEnabled(False)
