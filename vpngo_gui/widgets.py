"""Painted controls in the searxng language: state dot, route switch, icons."""

from PySide6.QtCore import Property, QByteArray, QEasingCurve, QPointF, QRectF, QSize, Qt, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QAbstractButton, QLabel, QSizePolicy, QToolButton, QWidget

from . import theme


ICONS = {
    "more": '<circle cx="5" cy="12" r="1.6" fill="{c}"/><circle cx="12" cy="12" r="1.6" fill="{c}"/>'
            '<circle cx="19" cy="12" r="1.6" fill="{c}"/>',
    "plus": '<path d="M12 5v14M5 12h14" stroke="{c}" stroke-width="2" stroke-linecap="round" fill="none"/>',
    "close": '<path d="M7 7l10 10M17 7L7 17" stroke="{c}" stroke-width="2" stroke-linecap="round" fill="none"/>',
    "down": '<path d="M12 5v14M6 13l6 6 6-6" stroke="{c}" stroke-width="2.2" stroke-linecap="round" '
            'stroke-linejoin="round" fill="none"/>',
    "up": '<path d="M12 19V5M6 11l6-6 6 6" stroke="{c}" stroke-width="2.2" stroke-linecap="round" '
          'stroke-linejoin="round" fill="none"/>',
    "clock": '<circle cx="12" cy="12" r="8" stroke="{c}" stroke-width="2" fill="none"/>'
             '<path d="M12 8v4l3 2" stroke="{c}" stroke-width="2" stroke-linecap="round" fill="none"/>',
    "layers": '<path d="M12 4l8 4-8 4-8-4 8-4z M4 12l8 4 8-4 M4 16l8 4 8-4" stroke="{c}" stroke-width="1.8" '
              'stroke-linejoin="round" stroke-linecap="round" fill="none"/>',
}


def icon_pixmap(name, color, size=18, ratio=2.0):
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">{ICONS[name].format(c=color)}</svg>'
    renderer = QSvgRenderer(QByteArray(svg.encode()))
    pixmap = QPixmap(int(size * ratio), int(size * ratio))
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    pixmap.setDevicePixelRatio(ratio)
    return pixmap


def icon(name, size=18):
    result = QIcon()
    result.addPixmap(icon_pixmap(name, theme.MUTED, size), QIcon.Mode.Normal)
    result.addPixmap(icon_pixmap(name, theme.TEXT, size), QIcon.Mode.Active)
    result.addPixmap(icon_pixmap(name, theme.mix(theme.MUTED, theme.BG, .45).name(), size), QIcon.Mode.Disabled)
    return result


class IconButton(QToolButton):
    """A 32px round ghost button, like the searxng home button."""

    def __init__(self, name, tooltip, parent=None):
        super().__init__(parent)
        self.setIcon(icon(name))
        self.setIconSize(QSize(18, 18))
        self.setFixedSize(32, 32)
        self.setToolTip(tooltip)
        self.setAccessibleName(tooltip)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAutoRaise(True)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.setStyleSheet(f"""
            QToolButton {{ border: 0; border-radius: 10px; background: transparent; }}
            QToolButton:hover, QToolButton:focus {{ background: {theme.FAINT}; }}
            QToolButton::menu-indicator {{ image: none; width: 0; }}""")


class PillButton(QAbstractButton):
    """A labelled pill with an icon, painted so icon and text sit exactly centred, like the summary pill."""

    def __init__(self, name, text, parent=None):
        super().__init__(parent)
        self.setText(text)
        self.icon_name = name
        self.setFixedHeight(34)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setAccessibleName(text)
        self.setFont(theme.font(13))

    def sizeHint(self):
        return QSize(int(15 + 16 * 16 / 24 + 8 + self.fontMetrics().tightBoundingRect(self.text()).width() + 15), 34)

    def enterEvent(self, event):
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        active = self.underMouse() or self.hasFocus() or self.isDown()
        border = theme.mix(theme.FAINT, theme.VPN, .5) if active else QColor(theme.FAINT)
        painter.setPen(QPen(border, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(rounded(QRectF(self.rect()).adjusted(.5, .5, -.5, -.5), 17))
        color = theme.TEXT if active else theme.MUTED
        # Centre the ink, not the boxes: the 24-unit icon art spans 4..20, and glyphs have side bearings.
        ink_pad, ink_width, gap = 16 * 4 / 24, 16 * 16 / 24, 8
        tight = self.fontMetrics().tightBoundingRect(self.text())
        start = (self.width() - (ink_width + gap + tight.width())) / 2
        painter.drawPixmap(QRectF(start - ink_pad, (self.height() - 16) / 2, 16, 16).toRect(),
                           icon_pixmap(self.icon_name, color, 16))
        painter.setPen(QColor(color))
        baseline = (self.height() + self.fontMetrics().capHeight()) / 2
        painter.drawText(QPointF(start + ink_width + gap - tight.left(), baseline), self.text())


class ElidedLabel(QLabel):
    """A one-line label that ends in "…" when it does not fit, with the full text as its tooltip."""

    def minimumSizeHint(self):
        return QSize(40, super().minimumSizeHint().height())

    def paintEvent(self, event):
        painter = QPainter(self)
        metrics = self.fontMetrics()
        text = metrics.elidedText(self.text(), Qt.TextElideMode.ElideRight, self.width())
        if text != self.text() and not self.toolTip():
            self.setToolTip(self.text())
        painter.setPen(self.palette().color(self.foregroundRole()))
        painter.drawText(self.rect(), int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), text)


class Rates(QWidget):
    """Download over upload, right-aligned in mono beside the app name, each with a drawn arrow."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFont(theme.font(12, mono=True))
        self.values = ("", "")
        # As wide as the widest rate ever shown, so the title's cut point never moves between refreshes.
        self.setFixedSize(self.fontMetrics().horizontalAdvance("000 kB/s") + 14, 28)

    def set_rates(self, down, up, tips=("", "")):
        if (down, up) != self.values:
            self.values = (down, up)
            self.setToolTip(f"{tips[0]}: {down}\n{tips[1]}: {up}" if down else "")
            self.update()

    def sizeHint(self):
        return self.size()

    def minimumSizeHint(self):
        return self.sizeHint()

    def paintEvent(self, event):
        if not self.values[0]:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        metrics = self.fontMetrics()
        for row, (name, text) in enumerate(zip(("down", "up"), self.values)):
            top = row * 14
            painter.drawPixmap(QRectF(self.width() - 10, top + 2, 10, 10).toRect(), icon_pixmap(name, theme.MUTED, 10))
            painter.setPen(QColor(theme.MUTED))
            painter.drawText(QPointF(self.width() - 14 - metrics.horizontalAdvance(text), top + 7 + metrics.capHeight() / 2),
                             text)


class TotalRate(QWidget):
    """Narrow tiles: download plus upload as one figure, marked by the drawn arrow pair, fixed width."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFont(theme.font(12, mono=True))
        self.text = ""
        self.setFixedSize(16 + 4 + self.fontMetrics().horizontalAdvance("000 kB/s"), 18)

    def set_text(self, text, tip=""):
        if text != self.text:
            self.text = text
            self.setToolTip(tip)
            self.update()

    def paintEvent(self, event):
        if not self.text:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        metrics = self.fontMetrics()
        x = self.width() - metrics.horizontalAdvance(self.text) - 20
        painter.drawPixmap(QRectF(x, 4, 10, 10).toRect(), icon_pixmap("down", theme.MUTED, 10))
        painter.drawPixmap(QRectF(x + 7, 4, 10, 10).toRect(), icon_pixmap("up", theme.MUTED, 10))
        painter.setPen(QColor(theme.MUTED))
        painter.drawText(QPointF(x + 20, (18 + metrics.capHeight()) / 2), self.text)


class ServerLabel(QLabel):
    """The VPN server address, masked until clicked; a second click hides it again."""

    revealed_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFont(theme.font(12, mono=True))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.revealed = False
        self.short = False
        self.host = self.port = None
        self.hover = False
        self.setFixedHeight(18)
        from .i18n import tr
        self.setAccessibleName(tr("server_name"))
        self.setAccessibleDescription(tr("server_tip"))

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self._render()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self._render()

    def set_short(self, short):
        """Narrow tiles mask with one bullet per hidden part, to leave room for the rate."""
        if short != self.short:
            self.short = short
            self._render()

    def set_endpoint(self, host, port):
        if (host, port) != (self.host, self.port):
            self.host, self.port = host, port
            self._render()

    def toggle(self):
        if self.host:
            self.revealed = not self.revealed
            self._render()
            self.revealed_changed.emit(self.revealed)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggle()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.toggle()
        else:
            super().keyPressEvent(event)

    def enterEvent(self, event):
        self.hover = True
        self._render()

    def leaveEvent(self, event):
        self.hover = False
        self._render()

    def _render(self):
        from .i18n import tr
        from .stats import masked
        if not self.host:
            self.setText("")
            self.setToolTip("")
            return
        self.setText(self.host if self.revealed else masked(self.host, short=self.short))
        self.setToolTip(tr("server_shown_tip", port=self.port or "—") if self.revealed else tr("server_tip"))
        color = (theme.mix(theme.FAINT, theme.VPN, .75).name() if self.hasFocus() else
                 theme.TEXT if self.hover else theme.MUTED)
        self.setStyleSheet(f"color: {color};")


class StateDot(QWidget):
    """The searxng mode dot: a 7px light with a 3px halo; hollow when stopped, breathing when busy."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(16, 16)
        self._color = QColor(theme.MUTED)
        self._hollow = True
        self._pulse = 0.0
        self._fade = QVariantAnimation(self, duration=600, easingCurve=QEasingCurve.Type.OutCubic)
        self._fade.valueChanged.connect(self._set_color)
        self._breath = QVariantAnimation(self, startValue=0.0, endValue=1.0, duration=1100, loopCount=-1)
        self._breath.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._breath.valueChanged.connect(self._set_pulse)

    def set_state(self, color, hollow=False, animate=True):
        self._hollow = hollow
        target = QColor(color)
        if animate and self.isVisible() and target != self._color:
            self._fade.stop()
            self._fade.setStartValue(self._color)
            self._fade.setEndValue(target)
            self._fade.start()
        else:
            self._set_color(target)

    def set_busy(self, busy):
        if busy and self._breath.state() != QVariantAnimation.State.Running:
            self._breath.start()
        elif not busy:
            self._breath.stop()
            self._set_pulse(0.0)

    def _set_color(self, value):
        self._color = QColor(value)
        self.update()

    def _set_pulse(self, value):
        # A triangle wave so the halo swells and settles once per cycle.
        self._pulse = 1 - abs(1 - 2 * float(value))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        center = QPointF(self.width() / 2, self.height() / 2)
        if self._hollow and not self._pulse:
            painter.setPen(QPen(theme.mix(theme.FAINT, theme.MUTED, .2), 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(center, 3.5, 3.5)
            return
        halo = QColor(self._color)
        halo.setAlphaF(.22 + .25 * self._pulse)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(halo)
        radius = 6.5 + 1.5 * self._pulse
        painter.drawEllipse(center, radius, radius)
        painter.setBrush(self._color)
        painter.drawEllipse(center, 3.5, 3.5)


class RouteSwitch(QAbstractButton):
    """The searxng switch: 34x20 track that fills with the route light when on."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedSize(38, 24)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._position = 0.0
        self._slide = QVariantAnimation(self, duration=200, easingCurve=QEasingCurve.Type.OutCubic)
        self._slide.valueChanged.connect(self._set_position)
        self.toggled.connect(self._animate)

    def set_checked_quietly(self, checked):
        """Reflect a refreshed state without emitting clicks."""
        if self.isChecked() == checked:
            return
        self.blockSignals(True)
        self.setChecked(checked)
        self.blockSignals(False)
        self._animate(checked)

    def _animate(self, checked):
        self._slide.stop()
        self._slide.setStartValue(self._position)
        self._slide.setEndValue(1.0 if checked else 0.0)
        self._slide.start()

    def _set_position(self, value):
        self._position = float(value)
        self.update()

    position = Property(float, lambda self: self._position, _set_position)

    def sizeHint(self):
        return QSize(38, 24)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        track = QRectF(2, 2, 34, 20)
        on = self._position
        enabled = self.isEnabled()
        fill = theme.mix(theme.FAINT, theme.mix(theme.FAINT, theme.VPN, .45).name(), on)
        if not enabled:
            fill = theme.mix(fill.name(), theme.BG, .4)
        if self.hasFocus():
            painter.setPen(QPen(theme.color(theme.VPN, .75), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(track.adjusted(-2, -2, 2, 2), 12, 12)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(fill)
        painter.drawRoundedRect(track, 10, 10)
        knob = theme.mix(theme.MUTED, theme.TEXT, on)
        if self.underMouse() and enabled:
            knob = theme.mix(knob.name(), "#ffffff", .25)
        if not enabled:
            knob = theme.mix(knob.name(), theme.BG, .45)
        painter.setBrush(knob)
        painter.drawEllipse(QRectF(5 + 14 * on, 5, 14, 14))

    def enterEvent(self, event):
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.update()
        super().leaveEvent(event)


def rounded(rect, radius):
    path = QPainterPath()
    path.addRoundedRect(rect, radius, radius)
    return path
