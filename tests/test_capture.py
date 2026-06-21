import numpy as np
import pytest
from ievr_bot.capture import StaticFrameSource, WindowCapture, find_window


def test_static_frame_source_returns_frame():
    frame = np.zeros((10, 10, 3), np.uint8)
    src = StaticFrameSource(frame)
    out = src.grab()
    assert out.shape == (10, 10, 3)
    assert np.array_equal(out, frame)


def test_window_capture_requires_title():
    with pytest.raises(ValueError):
        WindowCapture("")


def test_window_capture_grab_raises_when_window_missing():
    cap = WindowCapture("___no_such_window_zzz___")
    with pytest.raises(RuntimeError):
        cap.grab()


def test_find_window_missing_returns_none():
    assert find_window("___no_such_window_zzz___") is None
