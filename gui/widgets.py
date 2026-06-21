import numpy as np
from PySide6.QtWidgets import QGroupBox, QLabel, QVBoxLayout, QPlainTextEdit
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtCore import Qt


class StatusPanel(QGroupBox):
    def __init__(self):
        super().__init__("Status")
        self.state = QLabel("state: -")
        self.score = QLabel("score: -")
        self.matches = QLabel("matches: 0")
        self.action = QLabel("action: -")
        lay = QVBoxLayout(self)
        for w in (self.state, self.score, self.matches, self.action):
            lay.addWidget(w)

    def update_status(self, upd):
        self.state.setText(f"state: {upd.state.name}")
        self.score.setText(f"score: {upd.score:.2f}")
        self.matches.setText(f"matches: {upd.matches}")
        self.action.setText(f"action: {upd.action}")


class LogPanel(QGroupBox):
    def __init__(self):
        super().__init__("Log")
        self.text = QPlainTextEdit(readOnly=True)
        self.text.setMaximumBlockCount(500)
        lay = QVBoxLayout(self)
        lay.addWidget(self.text)

    def append(self, line: str):
        self.text.appendPlainText(line)


class PreviewPanel(QGroupBox):
    def __init__(self):
        super().__init__("Preview")
        self.label = QLabel("no frame")
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setMinimumSize(320, 180)
        lay = QVBoxLayout(self)
        lay.addWidget(self.label)

    def update_frame(self, frame: np.ndarray):
        if frame is None:
            return
        rgb = frame[:, :, ::-1].copy()  # BGR -> RGB
        h, w, _ = rgb.shape
        img = QImage(rgb.data, w, h, 3 * w, QImage.Format_RGB888)
        pix = QPixmap.fromImage(img).scaled(
            self.label.width(), self.label.height(),
            Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.label.setPixmap(pix)
