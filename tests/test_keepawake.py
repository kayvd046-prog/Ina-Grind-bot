"""Sleep prevention: while the bot runs, Windows must not go to sleep."""
from ievr_bot.keepawake import KeepAwake, ES_CONTINUOUS, ES_SYSTEM_REQUIRED


class RecordingSetter:
    def __init__(self):
        self.calls = []

    def __call__(self, flags):
        self.calls.append(flags)


def test_activate_requests_system_stays_awake():
    setter = RecordingSetter()
    ka = KeepAwake(setter=setter)
    ka.activate()
    assert setter.calls == [ES_CONTINUOUS | ES_SYSTEM_REQUIRED]


def test_deactivate_restores_normal_sleep_policy():
    setter = RecordingSetter()
    ka = KeepAwake(setter=setter)
    ka.activate()
    ka.deactivate()
    assert setter.calls[-1] == ES_CONTINUOUS


def test_context_manager_activates_and_deactivates():
    setter = RecordingSetter()
    with KeepAwake(setter=setter):
        assert setter.calls == [ES_CONTINUOUS | ES_SYSTEM_REQUIRED]
    assert setter.calls == [ES_CONTINUOUS | ES_SYSTEM_REQUIRED, ES_CONTINUOUS]


def test_setter_failure_never_propagates():
    def broken(flags):
        raise OSError("no kernel32 here")

    ka = KeepAwake(setter=broken)
    ka.activate()   # must not raise
    ka.deactivate()  # must not raise
