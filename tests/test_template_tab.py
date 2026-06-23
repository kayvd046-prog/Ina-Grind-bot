import os
import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
from PySide6.QtWidgets import QApplication
from ievr_bot.states import GameState
from ievr_bot.template_extractor import Candidate

app = QApplication.instance() or QApplication([])


def _cand(tag, crop):
    return Candidate(frame=np.full((60, 120, 3), tag, np.uint8), score=0.9, crop=crop)


def test_template_tab_constructs():
    from gui.template_tab import TemplateTab
    tab = TemplateTab()
    assert hasattr(tab, "log_line")
    assert callable(tab.save)
    assert callable(tab.diagnose)
    assert tab.diagnose_btn.text() == "Diagnose current screen"


def test_main_window_has_templates_tab():
    from gui.app import MainWindow
    win = MainWindow()
    tabs = win.centralWidget()
    titles = [tabs.tabText(i) for i in range(tabs.count())]
    assert "Run" in titles and "Templates" in titles


def test_state_row_with_candidates_selects_frame_and_crop():
    from gui.template_tab import StateRow
    row = StateRow(GameState.GOAL, [_cand(7, (10, 5, 40, 20))])
    sel = row.selected()
    assert sel is not None
    frame, crop = sel
    assert int(frame[0, 0, 0]) == 7
    assert crop == (10, 5, 40, 20)


def test_state_row_without_candidates_is_skipped():
    from gui.template_tab import StateRow
    row = StateRow(GameState.HALFTIME, [])
    assert row.skip.isChecked()
    assert row.selected() is None


def test_state_row_skip_toggle_returns_none():
    from gui.template_tab import StateRow
    row = StateRow(GameState.GOAL, [_cand(3, None)])
    row.skip.setChecked(True)
    assert row.selected() is None
