"""Dark theme + state colors for the IEVR GUI."""
from ievr_bot.states import GameState

ACCENT = "#3a6df0"
GREEN = "#34c759"
RED = "#ff453a"
BLUE = "#5ba7f7"
GRAY = "#8a8f98"

QSS = """
QWidget { background: #12141a; color: #e8eaf0; font-size: 13px;
          font-family: 'Segoe UI', sans-serif; }
QWidget#sidebar { background: #0c0e13; }
QLabel#appTitle { font-size: 17px; font-weight: 700; letter-spacing: 1px; }
QLabel#appSub { color: #8a8f98; font-size: 11px; }

QPushButton#nav { background: transparent; border: none; border-radius: 8px;
                  padding: 10px 14px; text-align: left; font-size: 14px;
                  color: #aab0bc; }
QPushButton#nav:hover { background: #171a22; color: #e8eaf0; }
QPushButton#nav:checked { background: #1d2740; color: #ffffff; font-weight: 600; }

QFrame#card { background: #1b1e27; border: 1px solid #262a35;
              border-radius: 12px; }
QLabel#cardTitle { color: #8a8f98; font-size: 11px; font-weight: 600;
                   letter-spacing: 1px; background: transparent; }
QLabel#cardValue { font-size: 26px; font-weight: 700; background: transparent; }
QLabel#cardSmall { font-size: 13px; background: transparent; color: #cdd2dc; }

QGroupBox { border: 1px solid #262a35; border-radius: 12px; margin-top: 12px;
            background: #1b1e27; font-weight: 600; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 4px;
                   color: #8a8f98; }

QPushButton { background: #262a35; border: none; padding: 9px 16px;
              border-radius: 8px; font-weight: 600; }
QPushButton:hover { background: #2e3342; }
QPushButton:disabled { background: #1b1e27; color: #565b66; }
QPushButton#start { background: #1f7a3d; }
QPushButton#start:hover { background: #249146; }
QPushButton#start:disabled { background: #1b1e27; color: #565b66; }
QPushButton#stop { background: #8a2b26; }
QPushButton#stop:hover { background: #a53730; }
QPushButton#stop:disabled { background: #1b1e27; color: #565b66; }

QComboBox { background: #262a35; border: none; border-radius: 8px;
            padding: 7px 12px; }
QComboBox::drop-down { border: none; width: 22px; }
QComboBox QAbstractItemView { background: #1b1e27; border: 1px solid #262a35;
                              selection-background-color: #1d2740; }
QCheckBox { spacing: 8px; }
QPlainTextEdit { background: #0c0e13; border: 1px solid #262a35;
                 border-radius: 8px; font-family: Consolas, monospace;
                 font-size: 12px; }
QScrollArea { border: none; }
"""

_STATE_COLORS = {
    GameState.IN_MATCH: GREEN,
    GameState.KICKOFF: GREEN,
    GameState.FOCUS_BATTLE: GREEN,
    GameState.ERROR_DIALOG: RED,
    GameState.UNKNOWN: GRAY,
}


def state_color(state: GameState) -> str:
    """Green while playing, red on errors, gray when unknown, blue for
    menus/transitions."""
    return _STATE_COLORS.get(state, BLUE)
