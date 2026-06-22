import threading
import numpy as np
from ievr_bot.recorder import MatchRecorder, RecordedFrame


class _Source:
    """Fake frame source: returns a distinct frame each grab; can raise once."""
    def __init__(self, raise_on=None):
        self.calls = 0
        self.raise_on = raise_on

    def grab(self):
        self.calls += 1
        if self.calls == self.raise_on:
            raise RuntimeError("transient grab failure")
        return np.full((4, 4, 3), self.calls, np.uint8)


def test_records_frames_until_stop_event():
    stop = threading.Event()
    sleeps = {"n": 0}

    def fake_sleep(_):
        sleeps["n"] += 1
        if sleeps["n"] >= 3:
            stop.set()

    rec = MatchRecorder(_Source(), interval=0.0, max_frames=100, sleep=fake_sleep)
    frames = rec.record(stop)
    assert len(frames) == 3
    assert all(isinstance(f, RecordedFrame) for f in frames)
    # frames are distinct grabs in order
    assert [int(f.frame[0, 0, 0]) for f in frames] == [1, 2, 3]


def test_stops_at_max_frames():
    stop = threading.Event()
    rec = MatchRecorder(_Source(), interval=0.0, max_frames=2, sleep=lambda _: None)
    frames = rec.record(stop)
    assert len(frames) == 2


def test_grab_exception_is_skipped_not_fatal():
    stop = threading.Event()
    src = _Source(raise_on=2)
    rec = MatchRecorder(src, interval=0.0, max_frames=2, sleep=lambda _: None)
    frames = rec.record(stop)
    # The failing grab (call #2) is skipped; recording continues to the cap.
    assert len(frames) == 2
    assert [int(f.frame[0, 0, 0]) for f in frames] == [1, 3]


def test_on_frame_callback_receives_each_frame():
    stop = threading.Event()
    seen = []
    rec = MatchRecorder(_Source(), interval=0.0, max_frames=2, sleep=lambda _: None)
    rec.record(stop, on_frame=lambda f: seen.append(int(f[0, 0, 0])))
    assert seen == [1, 2]
