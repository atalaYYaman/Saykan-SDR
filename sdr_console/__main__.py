"""Application entry point."""

from __future__ import annotations

import argparse
import sys

from PyQt6.QtWidgets import QApplication

from sdr_console.config.storage import load_config
from sdr_console.logging_setup import configure_logging
from sdr_console.ui.main_window import MainWindow
from sdr_console.ui.theme import apply_application_theme


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SDR Console")
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Logging level (DEBUG, INFO, WARNING, ERROR)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    configure_logging(args.log_level)

    app = QApplication(sys.argv)
    apply_application_theme(app)
    config = load_config()
    window = MainWindow(config=config)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
