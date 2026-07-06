"""Prevent Windows from sleeping while the bot grinds.

``SetThreadExecutionState`` with ``ES_CONTINUOUS`` applies per-thread and stays
in effect until the same thread clears it, so activate/deactivate must run on
the bot's worker thread (Orchestrator.run does this). Only the *system* is kept
awake — the display may still turn off, which is fine because capture uses
PrintWindow, not the screen.
"""
import ctypes
from typing import Callable, Optional

from .logger import get_logger

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001


def _win32_setter(flags: int) -> None:
    ctypes.windll.kernel32.SetThreadExecutionState(flags)


class KeepAwake:
    def __init__(self, setter: Optional[Callable[[int], None]] = None) -> None:
        self._setter = setter if setter is not None else _win32_setter

    def activate(self) -> None:
        self._call(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)

    def deactivate(self) -> None:
        self._call(ES_CONTINUOUS)

    def _call(self, flags: int) -> None:
        try:
            self._setter(flags)
        except Exception:
            get_logger().warning(
                "keep-awake call failed — Windows may go to sleep during "
                "long unattended runs")

    def __enter__(self) -> "KeepAwake":
        self.activate()
        return self

    def __exit__(self, *exc) -> bool:
        self.deactivate()
        return False
