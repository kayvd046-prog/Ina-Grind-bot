import time
from typing import Protocol, runtime_checkable


@runtime_checkable
class InputController(Protocol):
    def press(self, button: str, duration: float = 0.1) -> None: ...


class NullController:
    def __init__(self) -> None:
        self.presses: list[str] = []

    def press(self, button: str, duration: float = 0.1) -> None:
        self.presses.append(button)


class VGamepadController:
    def __init__(self, button_map: dict) -> None:
        import vgamepad as vg
        self._vg = vg
        self.pad = vg.VX360Gamepad()
        self.button_map = button_map
        self._lookup = {
            "A": vg.XUSB_BUTTON.XUSB_GAMEPAD_A,
            "B": vg.XUSB_BUTTON.XUSB_GAMEPAD_B,
            "X": vg.XUSB_BUTTON.XUSB_GAMEPAD_X,
            "Y": vg.XUSB_BUTTON.XUSB_GAMEPAD_Y,
            "START": vg.XUSB_BUTTON.XUSB_GAMEPAD_START,
            "LB": vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER,
            "RB": vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER,
        }

    def press(self, button: str, duration: float = 0.1) -> None:
        key = self.button_map[button]
        btn = self._lookup[key]
        self.pad.press_button(btn)
        self.pad.update()
        time.sleep(duration)
        self.pad.release_button(btn)
        self.pad.update()


class KeyboardController:
    def __init__(self, button_map: dict) -> None:
        import pydirectinput
        self._kb = pydirectinput
        self.button_map = button_map

    def press(self, button: str, duration: float = 0.1) -> None:
        key = self.button_map[button]
        self._kb.keyDown(key)
        time.sleep(duration)
        self._kb.keyUp(key)


def make_controller(kind: str, button_map: dict) -> InputController:
    if kind == "null":
        return NullController()
    if kind == "vgamepad":
        return VGamepadController(button_map)
    if kind == "keyboard":
        return KeyboardController(button_map)
    raise ValueError(f"Unknown controller kind: {kind}")
