import numpy as np
from ievr_bot.capture import StaticFrameSource


def test_static_frame_source_returns_frame():
    frame = np.zeros((10, 10, 3), np.uint8)
    src = StaticFrameSource(frame)
    out = src.grab()
    assert out.shape == (10, 10, 3)
    assert np.array_equal(out, frame)
