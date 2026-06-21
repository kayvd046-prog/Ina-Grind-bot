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
# Frames whose brightest channel is <= this are treated as all-black (failed
# PrintWindow on some GPU/DXGI titles) rather than a valid capture.
_BLACK_FRAME_MAX = 2


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


_HANDLE = ctypes.c_void_p  # 64-bit-safe handle type (HWND/HDC/HBITMAP/HGDIOBJ)
_winapi_configured = False


def _winapi():
    """Return (user32, gdi32) with argtypes/restypes set so every HWND and GDI
    handle is treated as a pointer-sized value. Without this, ctypes defaults
    handle args/returns to 32-bit ``int`` and overflows or truncates on 64-bit
    Windows when a handle exceeds 2**31. Idempotent."""
    global _winapi_configured
    u = ctypes.windll.user32
    g = ctypes.windll.gdi32
    if _winapi_configured:
        return u, g

    # user32 — window enumeration / lookup
    u.IsWindow.argtypes = [_HANDLE]
    u.IsWindow.restype = wintypes.BOOL
    u.IsWindowVisible.argtypes = [_HANDLE]
    u.IsWindowVisible.restype = wintypes.BOOL
    u.GetWindowTextLengthW.argtypes = [_HANDLE]
    u.GetWindowTextLengthW.restype = ctypes.c_int
    u.GetWindowTextW.argtypes = [_HANDLE, wintypes.LPWSTR, ctypes.c_int]
    u.GetWindowTextW.restype = ctypes.c_int
    u.EnumWindows.argtypes = [ctypes.c_void_p, wintypes.LPARAM]
    u.EnumWindows.restype = wintypes.BOOL
    # user32 — device contexts / capture
    u.GetWindowDC.argtypes = [_HANDLE]
    u.GetWindowDC.restype = _HANDLE
    u.ReleaseDC.argtypes = [_HANDLE, _HANDLE]
    u.ReleaseDC.restype = ctypes.c_int
    u.PrintWindow.argtypes = [_HANDLE, _HANDLE, wintypes.UINT]
    u.PrintWindow.restype = wintypes.BOOL
    u.GetClientRect.argtypes = [_HANDLE, ctypes.POINTER(wintypes.RECT)]
    u.GetClientRect.restype = wintypes.BOOL

    # gdi32 — bitmap blit (handle-returning fns must not truncate to int32)
    g.CreateCompatibleDC.argtypes = [_HANDLE]
    g.CreateCompatibleDC.restype = _HANDLE
    g.CreateCompatibleBitmap.argtypes = [_HANDLE, ctypes.c_int, ctypes.c_int]
    g.CreateCompatibleBitmap.restype = _HANDLE
    g.SelectObject.argtypes = [_HANDLE, _HANDLE]
    g.SelectObject.restype = _HANDLE
    g.GetDIBits.argtypes = [_HANDLE, _HANDLE, wintypes.UINT, wintypes.UINT,
                            ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT]
    g.GetDIBits.restype = ctypes.c_int
    g.DeleteObject.argtypes = [_HANDLE]
    g.DeleteObject.restype = wintypes.BOOL
    g.DeleteDC.argtypes = [_HANDLE]
    g.DeleteDC.restype = wintypes.BOOL

    _winapi_configured = True
    return u, g


def find_window(title_substring: str):
    """Return the HWND of the first visible window whose title contains
    title_substring (case-insensitive), or None."""
    user32, _ = _winapi()
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
        self._user32, self._gdi32 = _winapi()

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

        # Acquire each GDI/DC handle inside the try so a partial failure (e.g.
        # the window vanishing mid-grab) still releases whatever was obtained.
        # Over hours at ~2 grabs/s an unguarded leak would exhaust the GDI quota.
        hwnd_dc = mem_dc = bmp = old = None
        try:
            hwnd_dc = u.GetWindowDC(self.hwnd)
            if not hwnd_dc:
                raise RuntimeError("GetWindowDC failed (window gone?)")
            mem_dc = g.CreateCompatibleDC(hwnd_dc)
            if not mem_dc:
                raise RuntimeError("CreateCompatibleDC failed")
            bmp = g.CreateCompatibleBitmap(hwnd_dc, w, h)
            if not bmp:
                raise RuntimeError("CreateCompatibleBitmap failed")
            old = g.SelectObject(mem_dc, bmp)

            if not u.PrintWindow(self.hwnd, mem_dc, PW_RENDERFULLCONTENT):
                raise RuntimeError("PrintWindow failed")
            bmi = _BITMAPINFO()
            bmi.bmiHeader.biSize = ctypes.sizeof(_BITMAPINFOHEADER)
            bmi.bmiHeader.biWidth = w
            bmi.bmiHeader.biHeight = -h  # top-down
            bmi.bmiHeader.biPlanes = 1
            bmi.bmiHeader.biBitCount = 32
            bmi.bmiHeader.biCompression = _BI_RGB
            buf = (ctypes.c_char * (w * h * 4))()
            if g.GetDIBits(mem_dc, bmp, 0, h, buf, ctypes.byref(bmi), 0) == 0:
                raise RuntimeError("GetDIBits returned no scanlines")
            arr = np.frombuffer(buf, dtype=np.uint8).reshape(h, w, 4)
            frame = arr[:, :, :3].copy()  # BGRA -> BGR
            # GPU/DXGI titles sometimes hand PrintWindow an all-black surface.
            # Surface it as a failed grab so the loop backs off and the user
            # notices, instead of silently feeding a black frame to the detector.
            if int(frame.max()) <= _BLACK_FRAME_MAX:
                raise RuntimeError(
                    "PrintWindow returned an all-black frame; this game may need "
                    "capture_backend: screen"
                )
            return frame
        finally:
            if old:
                g.SelectObject(mem_dc, old)
            if bmp:
                g.DeleteObject(bmp)
            if mem_dc:
                g.DeleteDC(mem_dc)
            if hwnd_dc:
                u.ReleaseDC(self.hwnd, hwnd_dc)
