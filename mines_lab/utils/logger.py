"""
utils/logger.py — Centralised logging configuration.

All modules call get_logger(__name__) to obtain a namespaced logger.
Log output goes to data/mines_lab.log; console output is suppressed by
default so it doesn't interfere with the terminal UI.
"""

import logging
import os
from pathlib import Path

_LOG_PATH = Path(__file__).parent.parent / "data" / "mines_lab.log"
_initialised = False


def get_logger(name: str) -> logging.Logger:
    """Return a module-level logger, initialising the root handler once."""
    global _initialised

    logger = logging.getLogger(name)

    if not _initialised:
        _initialised = True
        _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

        fmt = logging.Formatter(
            "%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        # File handler — captures everything WARNING and above
        fh = logging.FileHandler(_LOG_PATH, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(fmt)

        root = logging.getLogger()
        root.setLevel(logging.DEBUG)
        root.addHandler(fh)

        # Suppress console output so Rich UI is not polluted
        root.propagate = False

    return logger
