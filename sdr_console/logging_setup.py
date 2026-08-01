"""Application-wide logging configuration."""

from __future__ import annotations

import logging
import sys


def configure_logging(level: str | int = "INFO") -> None:
    """Configure root logging for the SDR console process."""
    if isinstance(level, str):
        numeric = getattr(logging, level.upper(), None)
        if not isinstance(numeric, int):
            raise ValueError(f"Unknown log level: {level}")
        level = numeric

    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
        )
        root.addHandler(handler)
    root.setLevel(level)
