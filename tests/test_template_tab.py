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


def test_main_window_has_run_and_templates_pages():
    from gui.app import MainWindow
    win = MainWindow()
    # Sidebar navigation switches a stacked widget between the two pages.
    assert win.stack.count() == 2
    assert win.stack.widget(0) is win.run_page
    assert win.stack.widget(1) is win.template_tab
    assert win.nav_run.isChecked()
    win.nav_templates.click()
    assert win.stack.currentWidget() is win.template_tab


def test_status_update_colors_state_card():
    from gui.app import RunPage
    from ievr_bot.orchestrator import StatusUpdate
    page = RunPage()
    upd = StatusUpdate(state=GameState.IN_MATCH, score=0.9,
                       action="waiting", matches=3, frame=None)
    page.update_status(upd)
    assert page.state_card.value.text() == "IN_MATCH"
    assert page.matches_card.value.text() == "3"
    assert "#34c759" in page.state_card.value.styleSheet()  # green while playing


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


def test_run_page_has_stop_condition_controls():
    from gui.app import RunPage
    page = RunPage()
    # 0 means "no limit" for both controls.
    assert page.stop_matches.value() == 0
    assert page.stop_hours.value() == 0.0


def test_bot_worker_accepts_stop_limits():
    from gui.worker import BotWorker
    w = BotWorker(None, stop_after_matches=5, stop_after_seconds=3600.0)
    assert w.stop_after_matches == 5
    assert w.stop_after_seconds == 3600.0


def test_state_row_skip_toggle_returns_none():
    from gui.template_tab import StateRow
    row = StateRow(GameState.GOAL, [_cand(3, None)])
    row.skip.setChecked(True)
    assert row.selected() is None
