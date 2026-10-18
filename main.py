"""Точка входа RSS Reader."""
import sys

from PySide6.QtWidgets import QApplication

from rss_reader import APP_NAME, ORG_NAME, __version__
from rss_reader.ui.main_window import MainWindow


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORG_NAME)
    app.setApplicationVersion(__version__)
    app.setApplicationDisplayName(APP_NAME)
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
