"""Templates tab: record one match, auto-extract per-state candidates with the
bot's own detector, review/crop them, and save the reference PNGs."""
import numpy as np
from PySide6.QtWidgets import (
    QWidget, QGroupBox, QVBoxLayout, QHBoxLayout, QPushButton, QComboBox,
    QLabel, QCheckBox, QScrollArea, QSizePolicy,
)
from PySide6.QtGui import QImage, QPixmap, QPainter, QPen, QColor
from PySide6.QtCore import Qt, QThread, Signal, QRect

from ievr_bot.config import load_profile
from ievr_bot.paths import profiles_dir
from ievr_bot.states import GameState
from ievr_bot.template_extractor import extract_candidates, save_template
from gui.record_worker import RecordWorker


def _frame_to_pixmap(frame: np.ndarray) -> QPixmap:
    rgb = frame[:, :, ::-1].copy()  # BGR -> RGB
    h, w, _ = rgb.shape
    img = QImage(rgb.data, w, h, 3 * w, QImage.Format_RGB888)
    return QPixmap.fromImage(img.copy())


def _keywords_map(profile) -> dict:
    out = {}
    for name, words in (profile.ocr or {}).get("keywords", {}).items():
        try:
            out[GameState[name]] = list(words)
        except KeyError:
            continue
    return out


class _NullOcr:
    def read_boxes(self, frame):
        return []


class ExtractWorker(QThread):
    """Builds the detector + OCR engine and labels recorded frames off the UI
    thread (OCR over hundreds of frames can take a while)."""
    done = Signal(object)   # dict[GameState, list[Candidate]]
    error = Signal(str)

    def __init__(self, profile, frames):
        super().__init__()
        self.profile = profile
        self.frames = frames

    def run(self):
        try:
            from ievr_bot.composite_detector import build_detector
            detector = build_detector(self.profile)
            try:
                from ievr_bot.ocr import make_ocr_engine
                ocr = make_ocr_engine((self.profile.ocr or {}).get("lang", "en"))
            except Exception:
                ocr = _NullOcr()
            result = extract_candidates(self.frames, detector, ocr,
                                        _keywords_map(self.profile))
            self.done.emit(result)
        except Exception as exc:
            self.error.emit(str(exc))
            self.done.emit({})


class DiagnoseWorker(QThread):
    """Grabs ONE frame from the game window and reports what the bot sees:
    every OCR text line and the detected state. Saves the frame as a PNG."""
    done = Signal(str, str, object)   # report text, png path, frame
    error = Signal(str)

    def __init__(self, profile):
        super().__init__()
        self.profile = profile

    def _grab(self, source, tries=6, delay=0.4):
        import time
        last = None
        for _ in range(tries):
            try:
                return source.grab()
            except Exception as exc:
                last = exc
                time.sleep(delay)
        raise RuntimeError(str(last))

    def run(self):
        try:
            from ievr_bot.capture import build_frame_source
            from ievr_bot.composite_detector import build_detector
            from ievr_bot.diagnostics import diagnose_frame, format_report, save_frame
            from ievr_bot.paths import user_data_dir
            frame = self._grab(build_frame_source(self.profile))
            png = save_frame(frame, user_data_dir() / "diag")
            detector = build_detector(self.profile)
            try:
                from ievr_bot.ocr import make_ocr_engine
                ocr = make_ocr_engine((self.profile.ocr or {}).get("lang", "en"))
            except Exception:
                ocr = _NullOcr()
            report = format_report(diagnose_frame(frame, ocr, detector))
            self.done.emit(report, str(png), frame)
        except Exception as exc:
            self.error.emit(str(exc))


class CropView(QWidget):
    """Shows a frame scaled to fit and a draggable/resizable crop rectangle.
    Drag inside the box to move it; drag the bottom-right handle to resize."""
    _HANDLE = 14

    def __init__(self):
        super().__init__()
        self.setMinimumSize(360, 210)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._pix: QPixmap | None = None
        self._fw = self._fh = 1
        self._crop = (0, 0, 1, 1)  # frame coords x, y, w, h
        self._drag = None          # ("move", dx, dy) or ("resize",)

    def set_frame(self, frame: np.ndarray, crop):
        self._pix = _frame_to_pixmap(frame)
        self._fh, self._fw = frame.shape[:2]
        if crop is None:
            crop = (0, 0, self._fw, self._fh)
        self._crop = tuple(int(v) for v in crop)
        self.update()

    def get_crop(self):
        return self._crop

    # --- coordinate mapping between frame pixels and widget pixels ---
    def _geom(self):
        ww, wh = self.width(), self.height()
        scale = min(ww / self._fw, wh / self._fh)
        dw, dh = self._fw * scale, self._fh * scale
        ox, oy = (ww - dw) / 2, (wh - dh) / 2
        return scale, ox, oy

    def _to_widget(self, x, y):
        s, ox, oy = self._geom()
        return ox + x * s, oy + y * s

    def _to_frame(self, wx, wy):
        s, ox, oy = self._geom()
        return (wx - ox) / s, (wy - oy) / s

    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#141517"))
        if self._pix is None:
            return
        s, ox, oy = self._geom()
        p.drawPixmap(int(ox), int(oy), int(self._fw * s), int(self._fh * s),
                     self._pix)
        x, y, w, h = self._crop
        wx, wy = self._to_widget(x, y)
        ww_, wh_ = w * s, h * s
        p.setPen(QPen(QColor("#3a6df0"), 2))
        p.drawRect(QRect(int(wx), int(wy), int(ww_), int(wh_)))
        # bottom-right resize handle
        p.fillRect(int(wx + ww_ - self._HANDLE), int(wy + wh_ - self._HANDLE),
                   self._HANDLE, self._HANDLE, QColor("#3a6df0"))

    def mousePressEvent(self, e):
        x, y, w, h = self._crop
        wx, wy = self._to_widget(x, y)
        s, _, _ = self._geom()
        brx, bry = wx + w * s, wy + h * s
        px, py = e.position().x(), e.position().y()
        if abs(px - brx) <= self._HANDLE and abs(py - bry) <= self._HANDLE:
            self._drag = ("resize",)
        elif wx <= px <= brx and wy <= py <= bry:
            fx, fy = self._to_frame(px, py)
            self._drag = ("move", fx - x, fy - y)

    def mouseMoveEvent(self, e):
        if not self._drag:
            return
        fx, fy = self._to_frame(e.position().x(), e.position().y())
        x, y, w, h = self._crop
        if self._drag[0] == "move":
            nx = int(min(max(0, fx - self._drag[1]), self._fw - w))
            ny = int(min(max(0, fy - self._drag[2]), self._fh - h))
            self._crop = (nx, ny, w, h)
        else:  # resize from bottom-right
            nw = int(min(max(8, fx - x), self._fw - x))
            nh = int(min(max(8, fy - y), self._fh - y))
            self._crop = (x, y, nw, nh)
        self.update()

    def mouseReleaseEvent(self, _):
        self._drag = None


class StateRow(QGroupBox):
    """One game state: cycle its candidate frames, adjust the crop, or skip."""
    def __init__(self, state: GameState, candidates: list):
        super().__init__(state.name)
        self.state = state
        self.candidates = candidates
        self.idx = 0
        self.skip = QCheckBox("Skip")
        self.view = CropView()
        self.info = QLabel()

        prev_btn = QPushButton("◀ prev")
        next_btn = QPushButton("next ▶")
        prev_btn.clicked.connect(lambda: self._step(-1))
        next_btn.clicked.connect(lambda: self._step(1))

        nav = QHBoxLayout()
        nav.addWidget(prev_btn); nav.addWidget(next_btn)
        nav.addWidget(self.info); nav.addStretch(); nav.addWidget(self.skip)

        lay = QVBoxLayout(self)
        lay.addWidget(self.view)
        lay.addLayout(nav)

        if not candidates:
            self.skip.setChecked(True)
            self.skip.setEnabled(False)
            prev_btn.setEnabled(False); next_btn.setEnabled(False)
            self.info.setText("no candidate — skip or capture manually")
            self.view.setEnabled(False)
        else:
            self._show()

    def _step(self, delta):
        if not self.candidates:
            return
        self.idx = (self.idx + delta) % len(self.candidates)
        self._show()

    def _show(self):
        cand = self.candidates[self.idx]
        self.view.set_frame(cand.frame, cand.crop)
        self.info.setText(
            f"candidate {self.idx + 1}/{len(self.candidates)}  "
            f"score={cand.score:.2f}")

    def selected(self):
        """Return (frame, crop) to save, or None if skipped / no candidate."""
        if self.skip.isChecked() or not self.candidates:
            return None
        return self.candidates[self.idx].frame, self.view.get_crop()


# Order shown in the review grid.
_REVIEW_STATES = [
    GameState.MAIN_MENU, GameState.LOADING, GameState.KICKOFF,
    GameState.IN_MATCH, GameState.HALFTIME, GameState.GOAL,
    GameState.FULLTIME, GameState.REWARDS, GameState.POST_MATCH,
    GameState.REMATCH, GameState.ERROR_DIALOG,
]


class TemplateTab(QWidget):
    log_line = Signal(str)

    def __init__(self):
        super().__init__()
        self.profile = None
        self.rec_worker: RecordWorker | None = None
        self.ext_worker: ExtractWorker | None = None
        self.diag_worker: DiagnoseWorker | None = None
        self.rows: list[StateRow] = []

        self.profile_box = QComboBox(); self.profile_box.addItems(["pve", "ranked"])
        self.record_btn = QPushButton("Record")
        self.stop_btn = QPushButton("Stop"); self.stop_btn.setEnabled(False)
        self.diagnose_btn = QPushButton("Diagnose current screen")
        self.save_btn = QPushButton("Save templates"); self.save_btn.setEnabled(False)
        self.status = QLabel("Idle. Pick a profile and press Record, then play "
                             "one full match in Commander Mode.")
        self.status.setWordWrap(True)
        self.preview = QLabel("no frame"); self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumSize(320, 180)

        top = QHBoxLayout()
        top.addWidget(QLabel("Profile:")); top.addWidget(self.profile_box)
        top.addWidget(self.record_btn); top.addWidget(self.stop_btn)
        top.addWidget(self.diagnose_btn)
        top.addStretch(); top.addWidget(self.save_btn)

        self.grid_host = QWidget()
        self.grid_layout = QVBoxLayout(self.grid_host)
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setWidget(self.grid_host)

        root = QVBoxLayout(self)
        root.addLayout(top)
        root.addWidget(self.status)
        root.addWidget(self.preview)
        root.addWidget(scroll, 1)

        self.record_btn.clicked.connect(self.start_record)
        self.stop_btn.clicked.connect(self.stop_record)
        self.diagnose_btn.clicked.connect(self.diagnose)
        self.save_btn.clicked.connect(self.save)

    # --- diagnose a single screen ---
    def diagnose(self):
        self.profile = load_profile(self.profile_box.currentText(), profiles_dir())
        self.diagnose_btn.setEnabled(False)
        self.status.setText("Diagnosing current screen… (make sure the game is "
                            "on the screen you want to inspect)")
        self.diag_worker = DiagnoseWorker(self.profile)
        self.diag_worker.error.connect(self._on_diag_error)
        self.diag_worker.done.connect(self._on_diagnosed)
        self.diag_worker.start()

    def _on_diag_error(self, msg):
        self.diagnose_btn.setEnabled(True)
        self.status.setText(f"Diagnose failed: {msg}  (is the game window open "
                            f"and not minimized?)")

    def _on_diagnosed(self, report, png_path, frame):
        self.diagnose_btn.setEnabled(True)
        self._on_preview(frame)
        for line in report.splitlines():
            self.log_line.emit(line)
        self.log_line.emit(f"saved diagnosis frame -> {png_path}")
        self.status.setText(report + f"\n\nSaved screenshot: {png_path}\n"
                            f"(full text also in the Run tab's Log)")

    # --- recording ---
    def start_record(self):
        self.profile = load_profile(self.profile_box.currentText(), profiles_dir())
        self._clear_grid()
        self.save_btn.setEnabled(False)
        self.rec_worker = RecordWorker(self.profile)
        self.rec_worker.preview.connect(self._on_preview)
        self.rec_worker.count.connect(self._on_count)
        self.rec_worker.error.connect(lambda m: self.status.setText(f"Error: {m}"))
        self.rec_worker.done.connect(self._on_recorded)
        self.rec_worker.start()
        self.record_btn.setEnabled(False); self.stop_btn.setEnabled(True)
        self.status.setText("Recording… play one full match, then press Stop.")

    def stop_record(self):
        if self.rec_worker:
            self.stop_btn.setEnabled(False)
            self.status.setText("Stopping…")
            self.rec_worker.stop()

    def _on_preview(self, frame):
        rgb = frame[:, :, ::-1].copy()
        h, w, _ = rgb.shape
        img = QImage(rgb.data, w, h, 3 * w, QImage.Format_RGB888)
        self.preview.setPixmap(QPixmap.fromImage(img).scaled(
            self.preview.width(), self.preview.height(),
            Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def _on_count(self, n):
        self.status.setText(f"Recording… {n} frames. Press Stop when the match "
                            f"is over.")

    def _on_recorded(self, frames):
        self.record_btn.setEnabled(True); self.stop_btn.setEnabled(False)
        if not frames:
            self.status.setText("No frames recorded. Is the game window visible?")
            return
        self.status.setText(f"Recorded {len(frames)} frames. Extracting "
                            f"templates… (this can take a minute)")
        self.ext_worker = ExtractWorker(self.profile, frames)
        self.ext_worker.error.connect(lambda m: self.status.setText(f"Error: {m}"))
        self.ext_worker.done.connect(self._on_extracted)
        self.ext_worker.start()

    def _on_extracted(self, candidates: dict):
        self._clear_grid()
        self.rows = []
        for state in _REVIEW_STATES:
            row = StateRow(state, candidates.get(state, []))
            self.rows.append(row)
            self.grid_layout.addWidget(row)
        found = sum(1 for r in self.rows if r.candidates)
        self.status.setText(f"Found candidates for {found}/{len(self.rows)} "
                            f"states. Review, adjust crops, then Save templates.")
        self.save_btn.setEnabled(True)

    # --- saving ---
    def save(self):
        if not self.profile:
            return
        saved = 0
        for row in self.rows:
            sel = row.selected()
            if sel is None:
                continue
            frame, crop = sel
            dest = self.profile.templates_dir / f"{row.state.name.lower()}.png"
            save_template(frame, crop, dest)
            saved += 1
            self.log_line.emit(f"saved template {dest}")
        self.status.setText(f"Saved {saved} template(s) to "
                            f"{self.profile.templates_dir}.")

    def _clear_grid(self):
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self.rows = []
