"""Темы оформления: светлая и тёмная, генерация QSS-стиля."""
import winreg  # noqa: F401  (Windows-приложение)

LIGHT = {
    "bg": "#F2F3F6",
    "panel": "#FFFFFF",
    "card": "#FFFFFF",
    "border": "#E2E5EB",
    "text": "#1D2026",
    "secondary": "#68707D",
    "accent": "#2F6BDE",
    "accent_hover": "#4C82EA",
    "accent_text": "#FFFFFF",
    "hover": "rgba(47,107,222,0.08)",
    "selection": "rgba(47,107,222,0.16)",
}

DARK = {
    "bg": "#141519",
    "panel": "#1C1E24",
    "card": "#22242B",
    "border": "#2D3038",
    "text": "#E7EAF0",
    "secondary": "#9BA1AC",
    "accent": "#5B8CFF",
    "accent_hover": "#78A1FF",
    "accent_text": "#FFFFFF",
    "hover": "rgba(91,140,255,0.10)",
    "selection": "rgba(91,140,255,0.22)",
}


def theme_colors(name: str) -> dict:
    return DARK if name == "dark" else LIGHT


def detect_system_dark() -> bool:
    """Определить, включена ли тёмная тема в Windows."""
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        )
        value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        return value == 0
    except Exception:
        return False


_QSS = """
* { font-family: "Segoe UI", "Segoe UI Variable", sans-serif; }

QWidget { background: %(bg)s; color: %(text)s; font-size: 13px; }

QMainWindow { background: %(bg)s; }

QWidget#panel { background: %(panel)s; border-radius: 10px; }
QWidget#card  { background: %(card)s;  border-radius: 10px; }

QLabel { background: transparent; }
QLabel[role="caption"] { color: %(secondary)s; font-size: 11px; font-weight: bold; }
QLabel[role="secondary"] { color: %(secondary)s; }

QMenuBar { background: transparent; }
QMenuBar::item { padding: 6px 10px; border-radius: 6px; background: transparent; }
QMenuBar::item:selected { background: %(hover)s; }

QMenu { background: %(panel)s; border: 1px solid %(border)s; border-radius: 10px; padding: 6px; }
QMenu::item { padding: 7px 26px 7px 14px; border-radius: 6px; }
QMenu::item:selected { background: %(selection)s; }
QMenu::separator { height: 1px; background: %(border)s; margin: 6px 8px; }

QToolButton#iconButton {
    background: transparent; border: none; border-radius: 6px;
    padding: 4px 9px; color: %(secondary)s; font-size: 15px;
}
QToolButton#iconButton:hover { background: %(hover)s; color: %(text)s; }

QPushButton {
    background: %(card)s; border: 1px solid %(border)s; border-radius: 7px;
    padding: 6px 14px; color: %(text)s;
}
QPushButton:hover { background: %(hover)s; border-color: %(accent)s; }
QPushButton:pressed { background: %(selection)s; }
QPushButton:disabled { color: %(secondary)s; border-color: %(border)s; }
QPushButton#accentButton {
    background: %(accent)s; color: %(accent_text)s; border: none; font-weight: 600;
}
QPushButton#accentButton:hover { background: %(accent_hover)s; }
QPushButton#accentButton:pressed { background: %(accent)s; }

QListWidget { background: transparent; border: none; outline: none; }
QListWidget#feedList::item { padding: 8px 10px; border-radius: 7px; margin: 1px 4px; }
QListWidget#feedList::item:hover { background: %(hover)s; }
QListWidget#feedList::item:selected { background: %(selection)s; color: %(text)s; }
QListWidget#feedList::item:disabled { color: %(secondary)s; }

QTextEdit, QTextBrowser {
    background: %(panel)s; border: 1px solid %(border)s; border-radius: 8px;
    padding: 10px; selection-background-color: %(selection)s;
}

QGroupBox {
    background: %(card)s; border: 1px solid %(border)s; border-radius: 10px;
    margin-top: 14px; padding: 6px;
}
QGroupBox::title {
    subcontrol-origin: margin; subcontrol-position: top left; left: 12px;
    padding: 0 5px; color: %(secondary)s; font-weight: 600; background: %(card)s;
    border-radius: 5px;
}

QSlider::groove:horizontal { height: 5px; border-radius: 2px; background: %(border)s; }
QSlider::sub-page:horizontal { background: %(accent)s; border-radius: 2px; }
QSlider::handle:horizontal {
    width: 14px; height: 14px; margin: -5px 0; border-radius: 7px; background: %(accent)s;
}
QSlider::handle:horizontal:hover { background: %(accent_hover)s; }

QProgressBar { background: %(border)s; border: none; border-radius: 4px; }
QProgressBar::chunk { background: %(accent)s; border-radius: 4px; }

QTableWidget { background: transparent; border: none; gridline-color: transparent; }
QTableWidget::item { padding: 4px; }
QHeaderView::section {
    background: transparent; color: %(secondary)s; border: none;
    border-bottom: 1px solid %(border)s; padding: 6px 8px; font-weight: 600;
}

QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: %(border)s; border-radius: 4px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: %(secondary)s; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal { background: %(border)s; border-radius: 4px; min-width: 30px; }
QScrollBar::handle:horizontal:hover { background: %(secondary)s; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }

QSplitter::handle { background: transparent; }
QSplitter::handle:hover { background: %(hover)s; }
QSplitter::handle:horizontal { width: 7px; border-radius: 3px; }
QSplitter::handle:vertical { height: 7px; border-radius: 3px; }

QStatusBar { background: transparent; color: %(secondary)s; border-top: 1px solid %(border)s; }
QStatusBar::item { border: none; }

QToolTip {
    background: %(panel)s; color: %(text)s; border: 1px solid %(border)s;
    padding: 4px 8px; border-radius: 6px;
}

QMessageBox, QInputDialog { background: %(bg)s; }

QLineEdit, QComboBox {
    background: %(panel)s; border: 1px solid %(border)s; border-radius: 7px;
    padding: 6px 10px; color: %(text)s; selection-background-color: %(selection)s;
}
QLineEdit:focus { border-color: %(accent)s; }
QComboBox QAbstractItemView {
    background: %(panel)s; border: 1px solid %(border)s;
    selection-background-color: %(selection)s;
}
"""


def build_qss(c: dict) -> str:
    return _QSS % c
