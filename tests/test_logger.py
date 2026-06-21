import logging
from ievr_bot.logger import get_logger, BufferHandler


def test_buffer_handler_collects_and_callbacks():
    received = []
    handler = BufferHandler()
    handler.callback = received.append
    logger = logging.getLogger("test_ievr_buffer")
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)

    logger.info("hello")

    assert any("hello" in line for line in handler.records)
    assert any("hello" in line for line in received)


def test_get_logger_returns_singleton():
    a = get_logger()
    b = get_logger()
    assert a is b
