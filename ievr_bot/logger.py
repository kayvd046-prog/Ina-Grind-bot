import logging
from typing import Callable, Optional

from .paths import logs_dir as _logs_dir

_LOG_DIR = _logs_dir()
_logger: Optional[logging.Logger] = None
_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"


class BufferHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[str] = []
        self.callback: Optional[Callable[[str], None]] = None
        self.setFormatter(logging.Formatter(_FORMAT))

    def emit(self, record: logging.LogRecord) -> None:
        line = self.format(record)
        self.records.append(line)
        if self.callback:
            self.callback(line)


def get_logger(name: str = "ievr") -> logging.Logger:
    global _logger
    if _logger is not None:
        return _logger
    _LOG_DIR.mkdir(exist_ok=True)
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter(_FORMAT)
    fh = logging.FileHandler(_LOG_DIR / "ievr.log", encoding="utf-8")
    fh.setFormatter(fmt)
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(ch)
    logger.buffer = BufferHandler()  # type: ignore[attr-defined]
    logger.addHandler(logger.buffer)  # type: ignore[attr-defined]
    _logger = logger
    return logger
