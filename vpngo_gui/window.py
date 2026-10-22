"""The main window: one tile per app, lit by its route."""

from html import escape

from PySide6.QtCore import QEasingCurve, QPointF, QRectF, QSize, Qt, QTimer, QVariantAnimation, Signal
from PySide6.QtGui import (QAction, QActionGroup, QColor, QFont, QIcon, QKeySequence, QLinearGradient, QPainter,
                           QPainterPath, QPen, QRadialGradient, QShortcut)
from PySide6.QtWidgets import (QGridLayout, QHBoxLayout, QLabel, QMenu, QPushButton, QScrollArea, QSizePolicy,
                               QVBoxLayout, QWidget)

from . import theme
from .i18n import tr
from .stats import rate_text, split_endpoint, uptime_text
from .widgets import (ElidedLabel, IconButton, PillButton, Rates, RouteSwitch, ServerLabel, StateDot, TotalRate,
                      icon, rounded)


TILE_HEIGHT = 196
TILE_MIN_WIDTH = 210
SIDE = 7     # Room beside each tile; two of them make the 14px column gap.
TOP = 2      # Room above; with BELOW it makes the 22px row gap.
BELOW = 20   # Room below for the long soft shadow.


def state_color(state):
    return {"vpn": theme.VPN, "partial": theme.WARN}.get(state, theme.MUTED)


class Light:
    """A 0..1 value that eases toward its target; drives a tile's route light."""

    def __init__(self, owner, on_change):
        self.value = 0.0
        self.animation = QVariantAnimation(owner, duration=600, easingCurve=QEasingCurve.Type.OutCubic)
        self.animation.valueChanged.connect(lambda value: (setattr(self, "value", float(value)), on_change()))

    def go(self, target, animate=True):
        if abs(target - self.value) < 1e-3:
            return
        self.animation.stop()
        if not animate:
            self.value = target
            self.animation.valueChanged.emit(target)
            return
        self.animation.setStartValue(self.value)
        self.animation.setEndValue(float(target))
        self.animation.start()


class Tile(QWidget):
    """Shared painting: the searxng surface card with an inset highlight and a soft long shadow."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(TILE_HEIGHT + TOP + BELOW)
        self.setMinimumWidth(TILE_MIN_WIDTH + 2 * SIDE)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.light = Light(self, self.update)   # 1 on the VPN, 0 otherwise.
        self.alive = Light(self, self.update)   # 1 running, 0 stopped: a stopped tile sinks into the ground.
        self.alive.value = 1.0
        self.warn = 0.0
        self.hover = 0.0
        self.history = ()   # Recent total rates, oldest first: drawn as the tile's traffic trace.

    def card_rect(self):
        return QRectF(self.rect()).adjusted(SIDE, TOP, -SIDE, -BELOW)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        card = self.card_rect()
        alive = self.alive.value
        # Long soft shadow (searxng: 0 12px 32px -16px): translucent layers falling below the card.
        painter.setPen(Qt.PenStyle.NoPen)
        layers = 16
        for step in range(layers):
            fade = 1 - step / layers
            painter.setBrush(QColor(0, 0, 0, int(34 * alive * fade ** 1.4)))
            drop = 3 + step * 1.05  # Reaches about 18px below the card, fading the whole way.
            painter.drawPath(rounded(card.adjusted(4 + step * .35, drop, -4 - step * .35, drop), 14))
        light = self.light.value
        accent = theme.WARN if self.warn else theme.VPN
        strength = max(light, self.warn * .5)
        surface = theme.mix(theme.mix(theme.SURFACE, theme.BG, .6).name(), theme.SURFACE, alive)
        fill = QLinearGradient(card.topLeft(), card.bottomLeft())
        fill.setColorAt(0, theme.mix(surface.name(), accent, .08 * strength + .02 * self.hover))
        fill.setColorAt(1, surface)
        painter.setBrush(fill)
        border = theme.mix(theme.FAINT, accent, .45 * strength)
        if self.hover:
            border = theme.mix(border.name(), theme.MUTED if not strength else accent, .25 * self.hover)
        painter.setPen(QPen(border, 1))
        painter.drawPath(rounded(card.adjusted(.5, .5, -.5, -.5), 14))
        self._paint_trace(painter, card, theme.mix(theme.MUTED, accent, strength).name())
        painter.setPen(QPen(QColor(255, 255, 255, int(9 * alive)), 1))
        painter.drawLine(QPointF(card.left() + 14, card.top() + 1.5), QPointF(card.right() - 14, card.top() + 1.5))

    def _paint_trace(self, painter, card, color):
        """The last two minutes of traffic as a faint area behind the text, in the route's color."""
        from .stats import HISTORY, QUIET
        samples = list(self.history)
        # Half a window of history before drawing, and nothing for an idle app: a flat line reads as a divider.
        if len(samples) < HISTORY // 2 or self.alive.value < .5 or max(samples) < QUIET:
            return
        peak = max(max(samples), QUIET * 4)
        # Between the top row and the app name, so the trace never runs under text.
        band = QRectF(card.left() + 1, card.top() + 44, card.width() - 2, card.height() * .5 - 44)
        step = band.width() / (HISTORY - 1)
        start = band.right() - step * (len(samples) - 1)
        points = [QPointF(start + index * step, band.bottom() - band.height() * min(1.0, value / peak))
                  for index, value in enumerate(samples)]
        area = QPainterPath(QPointF(points[0].x(), band.bottom()))
        for point in points:
            area.lineTo(point)
        area.lineTo(QPointF(points[-1].x(), band.bottom()))
        area.closeSubpath()
        painter.save()
        painter.setClipPath(rounded(card, 14))
        fade = QLinearGradient(band.topLeft(), band.bottomLeft())
        fade.setColorAt(0, theme.color(color, .10))
        fade.setColorAt(1, theme.color(color, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(fade)
        painter.drawPath(area)
        line = QPainterPath(points[0])
        for point in points[1:]:
            line.lineTo(point)
        # The oldest end fades in, so a trace that has not filled the band yet has no hard start.
        stroke = QLinearGradient(QPointF(points[0].x(), 0), QPointF(points[0].x() + 40, 0))
        stroke.setColorAt(0, theme.color(color, 0))
        stroke.setColorAt(1, theme.color(color, .32))
        painter.setPen(QPen(stroke, 1.2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(line)
        painter.restore()

    def enterEvent(self, event):
        self.hover = 1.0
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.hover = 0.0
        self.update()
        super().leaveEvent(event)


class AppTile(Tile):
    action = Signal(str, str, object)  # app name, action, argument

    def __init__(self, app, parent=None):
        super().__init__(parent)
        self.name = app.name
        self.app = None
        self.profiles = ()
        self.busy = False
        outer = QVBoxLayout(self)
        outer.setContentsMargins(SIDE + 18, TOP + 14, SIDE + 14, BELOW + 16)
        outer.setSpacing(0)

        top = QHBoxLayout()
        top.setSpacing(6)
        self.dot = StateDot()
        top.addWidget(self.dot)
        self.uptime = ElidedLabel()
        self.uptime.setFont(theme.font(12, mono=True))
        self.uptime.setStyleSheet(f"color: {theme.MUTED};")
        self.uptime.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        top.addWidget(self.uptime, 1)
        self.more = IconButton("more", self.name)
        self.menu = QMenu(self.more)
        self.more.setMenu(self.menu)
        self.menu.aboutToShow.connect(self._fill_menu)
        top.addWidget(self.more)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(
            lambda point: not self.busy and self.menu.popup(self.mapToGlobal(point)))
        outer.addLayout(top)
        outer.addStretch()

        heading = QHBoxLayout()
        heading.setSpacing(10)
        self.title = ElidedLabel(self.name)
        self.title.setFont(theme.font(20, QFont.Weight.DemiBold))
        self.title.setStyleSheet(f"color: {theme.TEXT}; letter-spacing: -0.2px;")
        self.title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        heading.addWidget(self.title, 1)
        self.rates = Rates()
        heading.addWidget(self.rates, 0, Qt.AlignmentFlag.AlignBottom)
        outer.addLayout(heading)
        outer.addSpacing(2)
        stats = QHBoxLayout()
        stats.setSpacing(10)
        self.server = ServerLabel()
        self.server.revealed_changed.connect(lambda _: self._sync_compact())
        stats.addWidget(self.server)
        stats.addStretch()
        self.total = TotalRate()  # Narrow tiles: the combined rate sits here instead of beside the name.
        self.total.hide()
        stats.addWidget(self.total)
        outer.addLayout(stats)
        outer.addSpacing(6)

        row = QWidget()
        row.setFixedHeight(28)
        bottom = QHBoxLayout(row)
        bottom.setContentsMargins(0, 0, 0, 0)
        bottom.setSpacing(10)
        self.detail = QLabel()
        self.detail.setFont(theme.font(13))
        self.detail.setTextFormat(Qt.TextFormat.RichText)
        bottom.addWidget(self.detail, 1)
        self.switch = RouteSwitch()
        self.switch.clicked.connect(lambda checked: self.action.emit(self.name, "on" if checked else "off", None))
        bottom.addWidget(self.switch, 0, Qt.AlignmentFlag.AlignVCenter)
        self.start = QPushButton(tr("start"))
        self.start.setFixedHeight(28)
        self.start.setStyleSheet("QPushButton { height: 28px; padding: 0 14px; border-radius: 14px; }")
        self.start.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start.clicked.connect(lambda: self.action.emit(self.name, "start", None))
        bottom.addWidget(self.start)
        outer.addWidget(row)
        self.update_app(app, (), animate=False)

    def update_app(self, app, profiles, animate=True):
        self.app, self.profiles = app, profiles
        running = app.running
        self.dot.set_state(state_color(app.state), hollow=not running, animate=animate)
        self.light.go(1.0 if app.state == "vpn" else 0.0, animate)
        self.alive.go(1.0 if running else 0.0, animate)
        self.warn = 1.0 if app.state == "partial" else 0.0
        self.switch.setVisible(running)
        self.start.setVisible(not running)
        if running:
            self.switch.set_checked_quietly(app.state in {"vpn", "partial"})
        self.title.setStyleSheet(f"color: {theme.TEXT if running else theme.mix(theme.TEXT, theme.BG, .4).name()};"
                                 " letter-spacing: -0.2px;")
        self._show_detail()
        self.switch.setToolTip(tr("vpn_off") if self.switch.isChecked() else tr("vpn_on"))
        # A direct route does not leave through the VPN server, so its address would mislead there.
        through_vpn = app.state in {"vpn", "partial"}
        self.server.set_endpoint(*(split_endpoint(app.endpoint) if through_vpn else (None, None)))
        self.uptime.setText(uptime_text(app.started_at) if running else "")
        self.uptime.setToolTip(f"{tr('uptime_tip')} {uptime_text(app.started_at)}" if running and app.started_at else "")
        if not running:
            self.set_traffic(None, ())
        self.update()

    def set_traffic(self, rates, history):
        """rates: (down, up) bytes per second or None; history: recent totals for the trace."""
        self.history = tuple(history)
        if rates is None:
            self.rates.set_rates("", "")
            self.total.set_text("")
        else:
            self.rates.set_rates(rate_text(rates[0]), rate_text(rates[1]), (tr("download"), tr("upload")))
            self.total.set_text(rate_text(rates[0] + rates[1]), self.rates.toolTip())
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._sync_compact()

    def _sync_compact(self):
        """Below a 260px card the rates collapse to one total beside the server line; a revealed
        address needs that room, so the total steps aside until the address is masked again."""
        compact = self.card_rect().width() < 260
        self.rates.setVisible(not compact)
        self.total.setVisible(compact and not self.server.revealed)
        self.server.set_short(compact)

    def set_busy(self, label):
        """label names the action in progress (\"Starting…\"), or None when idle."""
        self.busy = label
        self.dot.set_busy(bool(label))
        for control in (self.switch, self.start, self.more):
            control.setEnabled(not label)
        self._show_detail()

    def _show_detail(self):
        app = self.app
        # The profile is data (mono); the route word is language (sans).
        word = self.busy or tr("state_" + app.state)
        color = theme.WARN if app.state == "partial" and not self.busy else theme.MUTED
        if not app.running and not self.busy:
            color = theme.mix(theme.MUTED, theme.BG, .3).name()
        self.detail.setText(f'<span style="font-family:\'{theme.MONO}\'; font-size:12px">{escape(app.shown_profile)}'
                            f'</span>&nbsp;&nbsp;·&nbsp;&nbsp;{escape(word)}')
        self.detail.setStyleSheet(f"color: {color};")

    def _fill_menu(self):
        self.menu.clear()
        app = self.app
        if app.running:
            self.menu.addAction(tr("restart"), lambda: self.action.emit(self.name, "start", None))
            self.menu.addAction(tr("stop"), lambda: self.action.emit(self.name, "stop", None))
        else:
            self.menu.addAction(tr("start"), lambda: self.action.emit(self.name, "start", None))
        if self.profiles:
            self.menu.addSeparator()
            add_profiles(self.menu, self.profiles, app.shown_profile,
                         lambda p: self.action.emit(self.name, "profile", p))


def add_profiles(menu, profiles, current, choose):
    """Profiles inline under a header, current one marked: one click from the open menu."""
    header = menu.addAction(tr("switch_profile"))
    header.setEnabled(False)
    group = QActionGroup(menu)
    for profile in profiles:
        item = QAction(profile, menu, checkable=True)
        item.setChecked(profile == current)
        item.triggered.connect(lambda _=False, p=profile: choose(p))
        group.addAction(item)
        menu.addAction(item)


class AddTile(QWidget):
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(TILE_HEIGHT + TOP + BELOW)
        self.setMinimumWidth(TILE_MIN_WIDTH + 2 * SIDE)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName(tr("add_app"))
        self.hover = False

    def enterEvent(self, event):
        self.hover = True
        self.update()

    def leaveEvent(self, event):
        self.hover = False
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.clicked.emit()
        else:
            super().keyPressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        card = QRectF(self.rect()).adjusted(SIDE + .5, TOP + .5, -SIDE - .5, -BELOW - .5)
        active = self.hover or self.hasFocus()
        border = theme.mix(theme.FAINT, theme.VPN, .45) if self.hasFocus() else \
            QColor(theme.mix(theme.FAINT, theme.MUTED, .35) if active else theme.FAINT)
        painter.setPen(QPen(border, 1, Qt.PenStyle.DashLine))
        painter.setBrush(QColor(255, 255, 255, 5) if active else Qt.BrushStyle.NoBrush)
        painter.drawPath(rounded(card, 14))
        color = theme.TEXT if active else theme.MUTED
        painter.setPen(QColor(color))
        painter.setFont(theme.font(14))
        metrics = painter.fontMetrics()
        text = tr("add_app")
        width = 18 + 8 + metrics.horizontalAdvance(text)
        left = card.center().x() - width / 2
        icon("plus").paint(painter, int(left), int(card.center().y() - 9), 18, 18,
                           mode=QIcon.Mode.Active if active else QIcon.Mode.Normal)
        painter.drawText(QPointF(left + 26, card.center().y() + metrics.ascent() / 2 - 1), text)


class EmptyState(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 0, 32, 48)
        layout.addStretch(2)
        self.title = QLabel()
        self.title.setFont(theme.font(20, QFont.Weight.DemiBold))
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.body = QLabel()
        self.body.setProperty("role", "muted")
        self.body.setWordWrap(True)
        self.body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.button = QPushButton()
        self.button.setProperty("primary", True)
        self.button.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(self.title)
        layout.addSpacing(6)
        layout.addWidget(self.body)
        layout.addSpacing(20)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(self.button)
        row.addStretch()
        layout.addLayout(row)
        layout.addStretch(3)

    def show_message(self, title, body, button=None):
        self.title.setText(title)
        self.body.setText(body)
        self.button.setVisible(bool(button))
        if button:
            self.button.setText(button)


class MessageBar(QWidget):
    """Result line floating at the bottom; errors stay until dismissed."""

    shown = Signal()
    hidden = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setVisible(False)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 8, 10)
        layout.setSpacing(12)
        self.dot = StateDot()
        self.text = QLabel()
        self.text.setWordWrap(True)
        self.text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.close_button = IconButton("close", tr("dismiss"))
        self.close_button.setPopupMode(IconButton.ToolButtonPopupMode.DelayedPopup)
        self.close_button.clicked.connect(self.hide)
        layout.addWidget(self.dot, 0, Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self.text, 1)
        layout.addWidget(self.close_button, 0, Qt.AlignmentFlag.AlignTop)
        self.timer = QTimer(self, singleShot=True, interval=6000)
        self.timer.timeout.connect(self.hide)
        self.error = False

    def hideEvent(self, event):
        super().hideEvent(event)
        self.hidden.emit()

    def show_message(self, text, error):
        self.error = error
        self.dot.set_state(theme.DANGER if error else theme.VPN, animate=False)
        self.text.setText(text)
        self.show()
        self.shown.emit()
        self.update()
        if error:
            self.timer.stop()
        else:
            self.timer.start()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(.5, .5, -.5, -.5)
        accent = theme.DANGER if self.error else theme.VPN
        painter.setPen(QPen(theme.mix(theme.FAINT, accent, .35), 1))
        painter.setBrush(theme.mix(theme.SURFACE, accent, .06))
        painter.drawPath(rounded(rect, 12))


class Summary(QWidget):
    """The searxng mode pill: dot plus how many apps are on the VPN."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 14, 0)
        layout.setSpacing(8)
        self.dot = StateDot()
        self.label = QLabel()
        self.label.setFont(theme.font(13))
        self.label.setStyleSheet(f"color: {theme.MUTED}; letter-spacing: .2px;")
        layout.addWidget(self.dot)
        layout.addWidget(self.label)
        self.setFixedHeight(34)

    def set_counts(self, on, total):
        self.setVisible(total > 0)
        self.label.setText(tr("summary", on=on, total=total) if on else tr("summary_none"))
        self.dot.set_state(theme.VPN if on else theme.MUTED, hollow=False)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor(theme.FAINT), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(rounded(QRectF(self.rect()).adjusted(.5, .5, -.5, -.5), 17))


class Board(QWidget):
    """Lays the tiles out in as many columns as fit, moving tiles instead of rebuilding them."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.grid = QGridLayout(self)
        self.base_bottom = 20 - BELOW + 8
        self.grid.setContentsMargins(20 - SIDE, 4, 20 - SIDE, self.base_bottom)
        self.grid.setSpacing(0)
        self.grid.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.items = []
        self.columns = 0

    def set_bottom_inset(self, inset):
        """Room under the last row (for the floating message bar); tiles never move."""
        margins = self.grid.contentsMargins()
        self.grid.setContentsMargins(margins.left(), margins.top(), margins.right(), self.base_bottom + inset)

    def set_items(self, items):
        if items == self.items:
            return
        self.items = items
        self.columns = 0
        self.relayout()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.relayout()

    def relayout(self):
        usable = self.width() - 2 * (20 - SIDE)
        columns = max(1, min(4, usable // (TILE_MIN_WIDTH + 2 * SIDE)))
        if columns == self.columns and all(self.grid.indexOf(item) >= 0 for item in self.items):
            return
        self.columns = columns
        while self.grid.count():
            self.grid.takeAt(0)
        for column in range(4):
            self.grid.setColumnStretch(column, 1 if column < columns else 0)
        for index, item in enumerate(self.items):
            self.grid.addWidget(item, index // columns, index % columns)
            item.show()


class Window(QWidget):
    app_action = Signal(str, str, object)
    add_app = Signal()
    add_profile = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("VPNGo")
        self.setWindowIcon(QIcon(str(theme.ASSETS / "vpngo.svg")))
        self.resize(760, 520)
        self.setMinimumSize(QSize(300, 360))
        self.glow = Light(self, self.update)
        self.tiles = {}
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        bar = QHBoxLayout()
        bar.setContentsMargins(20, 16, 20, 12)
        bar.setSpacing(8)
        wordmark = QLabel("VPNGo")
        wordmark.setFont(theme.font(15, QFont.Weight.DemiBold))
        wordmark.setStyleSheet("letter-spacing: -0.15px;")
        bar.addWidget(wordmark)
        bar.addStretch()
        self.summary = Summary()
        bar.addWidget(self.summary)
        self.profiles_button = PillButton("layers", tr("profiles"))
        self.profiles_menu = QMenu(self.profiles_button)
        self.profiles_button.clicked.connect(lambda: self.profiles_menu.popup(
            self.profiles_button.mapToGlobal(self.profiles_button.rect().bottomLeft())))
        bar.addWidget(self.profiles_button)
        layout.addLayout(bar)

        self.board = Board()
        self.add_tile = AddTile()
        self.add_tile.clicked.connect(self.add_app)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setWidget(self.board)
        self.scroll.viewport().setAutoFillBackground(False)
        self.board.setAutoFillBackground(False)
        layout.addWidget(self.scroll, 1)

        self.empty = EmptyState()
        self.empty.button.clicked.connect(self._empty_action)
        layout.addWidget(self.empty, 1)
        self.empty.hide()

        # Floats over the board's bottom edge, so a message never reflows the tiles.
        self.message = MessageBar(self)
        self.message.shown.connect(self._place_message)
        self.message.hidden.connect(lambda: self.board.set_bottom_inset(0))
        for keys in (QKeySequence(Qt.Key.Key_Escape), QKeySequence.StandardKey.Close):
            QShortcut(keys, self, activated=self.close)
        self.snapshot = None
        self._profiles = ()
        self._fill_profiles_menu(())

    def _empty_action(self):
        (self.add_profile if self.snapshot is not None and not self.snapshot.profiles else self.add_app).emit()

    def _fill_profiles_menu(self, profiles):
        self.profiles_menu.clear()
        for profile in profiles:
            item = self.profiles_menu.addAction(profile)
            item.setFont(theme.font(13, mono=True))
            item.setEnabled(False)
        if profiles:
            self.profiles_menu.addSeparator()
        self.profiles_menu.addAction(tr("add_profile"), self.add_profile.emit)

    def show_unavailable(self, text):
        self.scroll.hide()
        self.empty.show_message("VPNGo", text)
        self.empty.show()

    def show_snapshot(self, snapshot, animate=True):
        first = self.snapshot is None
        self.snapshot = snapshot
        animate = animate and not first
        if first or snapshot.profiles != self._profiles:
            self._profiles = snapshot.profiles
            self._fill_profiles_menu(snapshot.profiles)
        names = [app.name for app in snapshot.apps]
        for name in list(self.tiles):
            if name not in names:
                self.tiles.pop(name).deleteLater()
        for app in snapshot.apps:
            tile = self.tiles.get(app.name)
            if tile is None:
                tile = AppTile(app)
                tile.action.connect(self.app_action)
                self.tiles[app.name] = tile
            tile.update_app(app, snapshot.profiles, animate=animate)
        self.board.set_items([self.tiles[name] for name in names] + [self.add_tile])
        self.summary.set_counts(snapshot.on_vpn, len(snapshot.apps))
        self.glow.go(1.0 if snapshot.on_vpn else 0.0, animate)
        if not snapshot.profiles and not snapshot.apps:
            self.scroll.hide()
            self.empty.show_message(tr("no_profiles_title"), tr("no_profiles_body"), tr("add_profile"))
            self.empty.show()
        elif not snapshot.apps:
            self.scroll.hide()
            self.empty.show_message(tr("empty_title"), tr("empty_body"), tr("add_app"))
            self.empty.show()
        else:
            self.empty.hide()
            self.scroll.show()

    def set_traffic(self, rates, history):
        for name, tile in self.tiles.items():
            tile.set_traffic(rates.get(name), history.get(name, ()))

    def set_busy(self, labels):
        """labels maps an app name to the action in progress."""
        for name, tile in self.tiles.items():
            if tile.busy != labels.get(name):
                tile.set_busy(labels.get(name))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(theme.BG))
        # The searxng connection light: a faint glow at the top in the route color.
        gradient = QRadialGradient(QPointF(self.width() / 2, -self.height() * .1), self.width() * .8)
        light = theme.mix(theme.MUTED, theme.VPN, self.glow.value)
        light.setAlphaF(.05 + .07 * self.glow.value)
        gradient.setColorAt(0, light)
        gradient.setColorAt(.7, QColor(0, 0, 0, 0))
        painter.fillRect(self.rect(), gradient)

    def _place_message(self):
        width = self.width() - 40
        height = self.message.heightForWidth(width) if self.message.hasHeightForWidth() else self.message.sizeHint().height()
        self.message.setGeometry(20, self.height() - height - 16, width, height)
        self.message.raise_()
        self.board.set_bottom_inset(height + 16)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.message.isVisible():
            self._place_message()

    def showEvent(self, event):
        # Keep keyboard focus on the window itself so no control looks selected until Tab is used.
        super().showEvent(event)
        self.setFocus(Qt.FocusReason.OtherFocusReason)

    def closeEvent(self, event):
        if getattr(self, "keep_in_tray", False):
            event.ignore()
            self.hide()
        else:
            super().closeEvent(event)
