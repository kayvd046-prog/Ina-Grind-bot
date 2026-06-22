from ievr_bot.capture import build_frame_source, WindowCapture


class _Profile:
    def __init__(self, backend, title=""):
        self.capture_backend = backend
        self.window_title = title


def test_window_backend_builds_window_capture():
    src = build_frame_source(_Profile("window", "INAZUMA ELEVEN"))
    assert isinstance(src, WindowCapture)
    assert src.title == "INAZUMA ELEVEN"
