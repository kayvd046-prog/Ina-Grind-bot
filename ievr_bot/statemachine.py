from .states import GameState
from .config import Profile
from .controller import InputController


class StateMachine:
    def __init__(self, profile: Profile, controller: InputController) -> None:
        self.profile = profile
        self.controller = controller
        self.matches_completed = 0

    def handle(self, state: GameState) -> str:
        if state == GameState.KICKOFF:
            self.controller.press("commander_toggle")
            self.controller.press("confirm")
            return "kickoff: enabled commander mode"
        if state == GameState.POST_MATCH:
            self.matches_completed += 1
            self.controller.press("confirm")
            return "post-match: advancing, starting next match"
        if state == GameState.MAIN_MENU:
            self.controller.press("confirm")
            return "main menu: starting match"
        if state.is_terminal_screen():
            self.controller.press("confirm")
            return f"{state.name.lower()}: confirm"
        if state == GameState.ERROR_DIALOG:
            self.controller.press("cancel")
            return "error dialog: dismissed"
        return f"{state.name.lower()}: waiting"
