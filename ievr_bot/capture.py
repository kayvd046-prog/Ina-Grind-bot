"""Frame sources.

- ScreenCapture: grabs the visible screen (foreground only).
- WindowCapture: grabs a specific window by title via the Win32 PrintWindow
  API, so it works even when the game is behind other windows / alt-tabbed
  (as long as the window is not minimized). Some GPU-accelerated games may
  return black frames with PrintWindow; fall back to ScreenCapture then.
- StaticFrameSource: fixed frame for tests / replays.
"""
import ctypes
from ctypes import wintypes
from typing import Protocol
import numpy as np


class FrameSource(Protocol):
    def grab(self) -> np.ndarray: ...


class StaticFrameSource:
    def __init__(self, frame: np.ndarray) -> None:
        self._frame = frame

    def grab(self) -> np.ndarray:
        return self._frame


class ScreenCapture:
    def __init__(self, region: dict | None = None) -> None:
        import mss
        self._sct = mss.mss()
        self.region = region or self._sct.monitors[1]

    def grab(self) -> np.ndarray:
        shot = self._sct.grab(self.region)
        arr = np.array(shot)  # BGRA
        return arr[:, :, :3]  # drop alpha -> BGR


# --- Win32 background window capture -------------------------------------

PW_RENDERFULLCONTENT = 0x00000002
_BI_RGB = 0


class _BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class _BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", _BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]


def _user32():
    u = ctypes.windll.user32
    u.GetWindowDC.argtypes = [wintypes.HWND]
    u.GetWindowDC.restype = wintypes.HDC
    u.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
    u.PrintWindow.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.UINT]
    u.PrintWindow.restype = wintypes.BOOL
    u.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    return u


def find_window(title_substring: str):
    """Return the HWND of the first visible window whose title contains
    title_substring (case-insensitive), or None."""
    user32 = ctypes.windll.user32
    found = []
    needle = title_substring.lower()

    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def _cb(hwnd, _lparam):
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            if length:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                if needle in buf.value.lower():
                    found.append(hwnd)
                    return False
        return True

    user32.EnumWindows(WNDENUMPROC(_cb), 0)
    return found[0] if found else None


class WindowCapture:
    def __init__(self, title_substring: str) -> None:
        if not title_substring:
            raise ValueError("WindowCapture needs a non-empty window title")
        self.title = title_substring
        self.hwnd = None
        self._user32 = _user32()
        self._gdi32 = ctypes.windll.gdi32

    def _ensure_hwnd(self) -> None:
        if not self.hwnd or not self._user32.IsWindow(self.hwnd):
            self.hwnd = find_window(self.title)
            if not self.hwnd:
                raise RuntimeError(f"Game window not found: '{self.title}'")

    def grab(self) -> np.ndarray:
        self._ensure_hwnd()
        u, g = self._user32, self._gdi32
        rect = wintypes.RECT()
        u.GetClientRect(self.hwnd, ctypes.byref(rect))
        w, h = rect.right - rect.left, rect.bottom - rect.top
        if w <= 0 or h <= 0:
            raise RuntimeError("Game window has no client area (minimized?)")

        hwnd_dc = u.GetWindowDC(self.hwnd)
        mem_dc = g.CreateCompatibleDC(hwnd_dc)
        bmp = g.CreateCompatibleBitmap(hwnd_dc, w, h)
        old = g.SelectObject(mem_dc, bmp)
        try:
            u.PrintWindow(self.hwnd, mem_dc, PW_RENDERFULLCONTENT)
            bmi = _BITMAPINFO()
            bmi.bmiHeader.biSize = ctypes.sizeof(_BITMAPINFOHEADER)
            bmi.bmiHeader.biWidth = w
            bmi.bmiHeader.biHeight = -h  # top-down
            bmi.bmiHeader.biPlanes = 1
            bmi.bmiHeader.biBitCount = 32
            bmi.bmiHeader.biCompression = _BI_RGB
            buf = (ctypes.c_char * (w * h * 4))()
            g.GetDIBits(mem_dc, bmp, 0, h, buf, ctypes.byref(bmi), 0)
            arr = np.frombuffer(buf, dtype=np.uint8).reshape(h, w, 4)
            return arr[:, :, :3].copy()  # BGRA -> BGR
        finally:
            g.SelectObject(mem_dc, old)
            g.DeleteObject(bmp)
            g.DeleteDC(mem_dc)
            u.ReleaseDC(self.hwnd, hwnd_dc)
