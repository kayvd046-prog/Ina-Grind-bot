from enum import Enum, auto


class GameState(Enum):
    UNKNOWN = auto()
    MAIN_MENU = auto()
    LOADING = auto()
    KICKOFF = auto()
    IN_MATCH = auto()
    FOCUS_BATTLE = auto()
    HALFTIME = auto()
    GOAL = auto()
    FULLTIME = auto()
    REWARDS = auto()
    POST_MATCH = auto()
    ERROR_DIALOG = auto()

    def is_terminal_screen(self) -> bool:
        return self in {
            GameState.HALFTIME,
            GameState.GOAL,
            GameState.FULLTIME,
            GameState.REWARDS,
            GameState.POST_MATCH,
        }
