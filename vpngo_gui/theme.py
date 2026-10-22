"""The searxng site's palette and type, applied to Qt."""

from pathlib import Path

from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette


ASSETS = Path(__file__).resolve().parent / "assets"

BG = "#111113"
SURFACE = "#19191c"
FAINT = "#26262a"
TEXT = "#e9e7e2"
MUTED = "#8b8984"
VPN = "#4cc38a"        # The searxng "direct" green: here, an app on the VPN.
WARN = "#e0a458"       # Partial or unverifiable routes.
DANGER = "#e5736b"

SANS = "Inter"
MONO = "JetBrains Mono"


def color(value, alpha=1.0):
    result = QColor(value)
    result.setAlphaF(alpha)
    return result


def mix(first, second, amount):
    """Blend like CSS color-mix: amount of `second` over `first`."""
    a, b = QColor(first), QColor(second)
    return QColor.fromRgbF(*(a.getRgbF()[i] * (1 - amount) + b.getRgbF()[i] * amount for i in range(3)),
                           a.alphaF() * (1 - amount) + b.alphaF() * amount)


def load_fonts():
    for name in ("Inter.woff2", "JetBrainsMono.woff2"):
        QFontDatabase.addApplicationFont(str(ASSETS / "fonts" / name))


def font(size, weight=QFont.Weight.Normal, mono=False):
    result = QFont(MONO if mono else SANS)
    result.setPixelSize(size)
    result.setWeight(weight)
    # The bundled faces are variable fonts with a single named instance; weight lives on the axis.
    result.setVariableAxis(QFont.Tag("wght"), float(weight.value if hasattr(weight, "value") else weight))
    result.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    if not mono:
        result.setFeature(QFont.Tag("cv11"), 1)
        result.setFeature(QFont.Tag("ss03"), 1)
    return result


def palette():
    result = QPalette()
    roles = {
        QPalette.ColorRole.Window: BG, QPalette.ColorRole.Base: BG, QPalette.ColorRole.AlternateBase: SURFACE,
        QPalette.ColorRole.Text: TEXT, QPalette.ColorRole.WindowText: TEXT, QPalette.ColorRole.Button: SURFACE,
        QPalette.ColorRole.ButtonText: TEXT, QPalette.ColorRole.Highlight: mix(FAINT, VPN, .34).name(),
        QPalette.ColorRole.HighlightedText: "#ffffff", QPalette.ColorRole.ToolTipBase: SURFACE,
        QPalette.ColorRole.ToolTipText: TEXT, QPalette.ColorRole.PlaceholderText: MUTED,
        QPalette.ColorRole.Link: TEXT,
    }
    for role, value in roles.items():
        result.setColor(role, QColor(value))
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.WindowText, QPalette.ColorRole.ButtonText):
        result.setColor(QPalette.ColorGroup.Disabled, role, QColor(MUTED))
    return result


STYLE = f"""
QWidget {{ color: {TEXT}; }}
QToolTip {{ background: {SURFACE}; color: {TEXT}; border: 1px solid {FAINT}; border-radius: 8px; padding: 6px 9px; }}

QMenu {{ background: {SURFACE}; border: 1px solid {FAINT}; border-radius: 12px; padding: 6px; }}
QMenu::item {{ padding: 8px 28px 8px 12px; border-radius: 8px; font-size: 13px; }}
QMenu::item:selected {{ background: {FAINT}; }}
QMenu::item:disabled {{ color: {MUTED}; }}
QMenu::separator {{ height: 1px; background: {FAINT}; margin: 6px 4px; }}
QMenu::indicator {{ width: 14px; height: 14px; left: 8px; }}
QMenu::indicator:checked {{ image: url({(ASSETS / "dot.svg").as_posix()}); }}
QMenu::item:checkable {{ padding-left: 30px; }}

QPushButton {{ height: 34px; padding: 0 16px; border: 1px solid {FAINT}; border-radius: 17px;
              background: transparent; color: {MUTED}; font-size: 13px; }}
QPushButton:hover {{ color: {TEXT}; border-color: {mix(FAINT, VPN, .5).name()}; }}
QPushButton:pressed {{ background: {FAINT}; }}
QPushButton:disabled {{ color: {mix(MUTED, BG, .45).name()}; border-color: {FAINT}; }}
QPushButton:focus {{ border-color: {mix(FAINT, VPN, .75).name()}; }}
QPushButton[primary="true"] {{ background: {TEXT}; border-color: {TEXT}; color: {BG}; font-weight: 600; }}
QPushButton[primary="true"]:hover {{ background: #ffffff; border-color: #ffffff; color: {BG}; }}
QPushButton[primary="true"]:disabled {{ background: {FAINT}; border-color: {FAINT}; color: {MUTED}; }}

QLineEdit, QComboBox {{ min-height: 36px; padding: 0 12px; border: 1px solid {FAINT}; border-radius: 10px;
                       background: {BG}; color: {TEXT}; selection-background-color: {mix(FAINT, VPN, .45).name()}; }}
QLineEdit:focus, QComboBox:focus, QComboBox:on {{ border-color: {mix(FAINT, VPN, .45).name()}; }}
QLineEdit[mono="true"] {{ font-family: "{MONO}"; font-size: 13px; }}
QComboBox::drop-down {{ border: 0; width: 28px; }}
QComboBox::down-arrow {{ image: url({(ASSETS / "chevron.svg").as_posix()}); width: 12px; height: 12px; }}
QComboBox QAbstractItemView {{ background: {SURFACE}; border: 1px solid {FAINT}; border-radius: 10px; padding: 4px;
                               outline: 0; selection-background-color: {FAINT}; }}

QCheckBox {{ spacing: 10px; color: {TEXT}; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border: 1px solid {mix(FAINT, MUTED, .35).name()}; border-radius: 5px;
                       background: {BG}; }}
QCheckBox::indicator:hover {{ border-color: {mix(FAINT, VPN, .5).name()}; }}
QCheckBox::indicator:checked {{ background: {VPN}; border-color: {VPN};
                               image: url({(ASSETS / "check.svg").as_posix()}); }}
QCheckBox:focus {{ outline: none; }}
QLabel[role="field"] {{ color: {MUTED}; font-size: 12px; }}
QLabel[role="muted"] {{ color: {MUTED}; }}

QScrollArea {{ border: 0; background: transparent; }}
QScrollBar:vertical {{ width: 10px; background: transparent; margin: 4px 2px; }}
QScrollBar::handle:vertical {{ background: {FAINT}; border-radius: 3px; min-height: 32px; }}
QScrollBar::handle:vertical:hover {{ background: {mix(FAINT, MUTED, .4).name()}; }}
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{ height: 0; background: none; }}

QDialog {{ background: {SURFACE}; }}
"""
