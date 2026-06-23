from ievr_bot.states import GameState


def test_all_expected_states_exist():
    names = {s.name for s in GameState}
    assert {"UNKNOWN", "MAIN_MENU", "LOADING", "KICKOFF", "IN_MATCH",
            "FOCUS_BATTLE", "HALFTIME", "GOAL", "FULLTIME", "REWARDS",
            "POST_MATCH", "REMATCH", "ERROR_DIALOG"} <= names


def test_terminal_screens():
    assert GameState.HALFTIME.is_terminal_screen()
    assert GameState.REWARDS.is_terminal_screen()
    assert GameState.REMATCH.is_terminal_screen()
    assert not GameState.IN_MATCH.is_terminal_screen()
    assert not GameState.UNKNOWN.is_terminal_screen()
