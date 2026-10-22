"""The main window: one tile per app, lit by its route, gathered under its group."""

import time
from html import escape

from PySide6.QtCore import QEasingCurve, QPointF, QRectF, QSize, Qt, QTimer, QVariantAnimation, Signal
from PySide6.QtGui import (QAction, QActionGroup, QColor, QFont, QIcon, QKeySequence, QLinearGradient, QPainter,
                           QPainterPath, QPen, QRadialGradient, QShortcut)
from PySide6.QtWidgets import (QGridLayout, QHBoxLayout, QLabel, QMenu, QPushButton, QScrollArea, QSizePolicy,
                               QVBoxLayout, QWidget)

from . import theme
from .appicons import app_icon
from .i18n import tr
from .stats import bytes_text, duration_text, rate_text, split_endpoint, uptime_text
from .widgets import (ElidedLabel, IconButton, PillButton, Rates, RouteClocks, RouteSwitch, ServerLabel, StateDot,
                      TotalRate, icon, rounded)


TILE_HEIGHT = 196
TILE_MIN_WIDTH = 210
HEADER_HEIGHT = 46
SIDE = 7     # Room beside each tile; two of them make the 14px column gap.
TOP = 2      # Room above; with BELOW it makes the 22px row gap.
BELOW = 20   # Room below for the long soft shadow.


def state_color(state):
    return {"vpn": theme.VPN, "partial": theme.WARN}.get(state, theme.MUTED)


def route_clocks(app):
    """((route, seconds), ...) for the top row: the time on the VPN and on the direct route.

    vpngo before 0.7.0 reports neither; then the one clock is the time since the app started.
    """
    if not app.running:
        return ()
    if app.vpn_seconds is not None and app.direct_seconds is not None:
        return (("vpn", app.vpn_seconds), ("direct", app.direct_seconds))
    since = app.route_since or app.started_at
    return ((("direct" if app.state == "direct" else "vpn"), time.time() - since),) if since else ()


def route_tip(app):
    """The clocks' tooltip: this route's time, both totals, the data on this route, and the open time."""
    since = app.route_since or app.started_at
    if not app.running or not since:
        return ""
    current = uptime_text(since)
    lines = [tr({"vpn": "on_vpn_for", "direct": "direct_for"}.get(app.state, "partial_for"), time=current)]
    if app.vpn_seconds is not None:
        lines += [tr("total_vpn", time=duration_text(app.vpn_seconds)),
                  tr("total_direct", time=duration_text(app.direct_seconds))]
    if app.route_rx_bytes is not None:
        lines.append(f"{tr('fact_data')}: ↓ {bytes_text(app.route_rx_bytes)} ↑ {bytes_text(app.route_tx_bytes or 0)}")
    if app.started_at:
        lines.append(tr("open_for", time=uptime_text(app.started_at)))
    return "\n".join(lines)


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
        self.history = ()   # (total rate, route) samples, oldest first: drawn as the tile's traffic trace.

    def card_rect(self):
        return QRectF(self.rect()).adjusted(SIDE, TOP, -SIDE, -BELOW)

    def trace_band(self, card):
        """Between the top row and the app name, so the trace never runs under text."""
        return QRectF(card.left() + 1, card.top() + 44, card.width() - 2, card.height() * .5 - 44)

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
        self._paint_trace(painter, card)
        painter.setPen(QPen(QColor(255, 255, 255, int(9 * alive)), 1))
        painter.drawLine(QPointF(card.left() + 14, card.top() + 1.5), QPointF(card.right() - 14, card.top() + 1.5))

    def _paint_trace(self, painter, card):
        """Recent traffic as a faint area behind the text: green where it went through the VPN,
        grey where it went direct, amber where the route was incomplete."""
        from .stats import HISTORY, QUIET
        span = HISTORY
        samples = list(self.history)[-span:]
        values = [value for value, _ in samples]
        # Half a tile's window of history before drawing, and nothing for an idle app: a flat line reads as a divider.
        if len(samples) < HISTORY // 2 or self.alive.value < .5 or max(values) < QUIET:
            return
        peak = max(max(values), QUIET * 4)
        band = self.trace_band(card)
        step = band.width() / (span - 1)
        start = band.right() - step * (len(samples) - 1)
        points = [QPointF(start + index * step, band.bottom() - band.height() * min(1.0, value / peak))
                  for index, value in enumerate(values)]
        runs, first = [], 0
        for index in range(1, len(samples) + 1):
            if index == len(samples) or samples[index][1] != samples[first][1]:
                runs.append((samples[first][1], first, index - 1))
                first = index
        painter.save()
        painter.setClipPath(rounded(card, 14))
        for state, first, last in runs:
            color = state_color(state)
            # Green carries the most meaning (the app is protected), so it reads a step stronger than grey.
            area_alpha, line_alpha = (.16, .55) if state == "vpn" else (.10, .32)
            # Each stretch starts at the previous one's last point, so the line never breaks.
            stretch = points[max(0, first - 1):last + 1]
            if len(stretch) < 2:
                continue
            area = QPainterPath(QPointF(stretch[0].x(), band.bottom()))
            for point in stretch:
                area.lineTo(point)
            area.lineTo(QPointF(stretch[-1].x(), band.bottom()))
            area.closeSubpath()
            fade = QLinearGradient(band.topLeft(), band.bottomLeft())
            fade.setColorAt(0, theme.color(color, area_alpha))
            fade.setColorAt(1, theme.color(color, 0))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(fade)
            painter.drawPath(area)
            line = QPainterPath(stretch[0])
            for point in stretch[1:]:
                line.lineTo(point)
            # The oldest end fades in, so a trace that has not filled the band yet has no hard start.
            stroke = QLinearGradient(QPointF(points[0].x(), 0), QPointF(points[0].x() + 40, 0))
            stroke.setColorAt(0, theme.color(color, 0))
            stroke.setColorAt(1, theme.color(color, line_alpha))
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
        self.groups = ()
        self.platform = ""
        self.busy = False
        outer = QVBoxLayout(self)
        outer.setContentsMargins(SIDE + 18, TOP + 14, SIDE + 14, BELOW + 16)
        outer.setSpacing(0)

        top = QHBoxLayout()
        top.setSpacing(6)
        self.dot = StateDot()
        top.addWidget(self.dot)
        self.clocks = RouteClocks()
        top.addWidget(self.clocks, 1, Qt.AlignmentFlag.AlignVCenter)
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
        self.icon = QLabel()
        self.icon.setFixedSize(24, 24)
        self.icon.hide()
        heading.addWidget(self.icon, 0, Qt.AlignmentFlag.AlignVCenter)
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
        self.server.lookup_requested.connect(lambda: self.action.emit(self.name, "lookup", None))
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

    def update_app(self, app, profiles, groups=(), platform="", manages=False, animate=True):
        """manages: vpngo can group and remove apps (0.7.0 and later)."""
        first = self.app is None
        self.app, self.profiles, self.groups, self.platform = app, profiles, groups, platform
        self.manages = manages
        running = app.running
        self.dot.set_state(state_color(app.state), hollow=not running, animate=animate)
        self.light.go(1.0 if app.state == "vpn" else 0.0, animate)
        self.alive.go(1.0 if running else 0.0, animate)
        self.warn = 1.0 if app.state == "partial" else 0.0
        self.switch.setVisible(running)
        self.start.setVisible(not running)
        if running:
            self.switch.set_checked_quietly(app.state in {"vpn", "partial"})
        dim = theme.mix(theme.TEXT, theme.BG, .4).name()
        self.title.setStyleSheet(f"color: {theme.TEXT if running else dim}; letter-spacing: -0.2px;")
        if first or app.executable != getattr(self, "_executable", None):
            self._executable = app.executable
            found = app_icon(app.name, app.executable)
            self.icon.setVisible(found is not None)
            if found is not None:
                self.icon.setPixmap(found.pixmap(QSize(24, 24), self.devicePixelRatioF()))
        self.icon.setEnabled(running)
        self._show_detail()
        self.switch.setToolTip(tr("vpn_off") if self.switch.isChecked() else tr("vpn_on"))
        # A direct route does not leave through the VPN server: there the line is the public IP instead.
        if app.state in {"vpn", "partial"}:
            self.server.set_endpoint(*split_endpoint(app.endpoint))
        elif app.state == "direct":
            self.server.set_public(getattr(self, "public_ip", None))
        else:
            self.server.set_endpoint(None, None)
        self.clocks.set_clocks(route_clocks(app), "direct" if app.state == "direct" else "vpn", route_tip(app))
        if not running:
            self.set_traffic(None, ())
        self.update()

    def set_public_ip(self, address, failed=False):
        self.public_ip = address
        if failed:
            self.server.lookup_failed()
        elif self.app and self.app.state == "direct":
            self.server.set_public(address)

    def set_traffic(self, rates, history):
        """rates: (down, up) bytes per second or None; history: recent (total, route) samples for the trace."""
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
        emit = self.action.emit
        if app.running:
            self.menu.addAction(tr("restart"), lambda: emit(self.name, "start", None))
            self.menu.addAction(tr("stop"), lambda: emit(self.name, "stop", None))
        else:
            self.menu.addAction(tr("start"), lambda: emit(self.name, "start", None))
        if self.profiles:
            self.menu.addSeparator()
            add_profiles(self.menu, self.profiles, app.shown_profile, lambda p: emit(self.name, "profile", p))
        if self.manages:
            self.menu.addSeparator()
            self._fill_group_menu(self.menu.addMenu(tr("group_menu")))
        if self.platform.startswith("linux"):
            # Linux only: the other systems cannot enforce either safeguard per app.
            self.menu.addSeparator()
            header = self.menu.addAction(tr("protection"))
            header.setEnabled(False)
            killswitch = QAction(tr("killswitch"), self.menu, checkable=True, checked=app.killswitch)
            killswitch.setEnabled(not app.dns)  # DNS isolation depends on it.
            killswitch.triggered.connect(lambda on: emit(self.name, "policy", ("killswitch", on)))
            self.menu.addAction(killswitch)
            dns = QAction(tr("dns_isolation"), self.menu, checkable=True, checked=app.dns)
            dns.setEnabled(app.killswitch)
            dns.triggered.connect(lambda on: emit(self.name, "policy", ("dns", on)))
            self.menu.addAction(dns)
        if self.manages and not app.running:
            self.menu.addSeparator()
            self.menu.addAction(tr("remove_app"), lambda: emit(self.name, "remove", None))

    def _fill_group_menu(self, groups):
        app, emit = self.app, self.action.emit
        choice = QActionGroup(groups)
        for group in self.groups:
            item = QAction(group, groups, checkable=True)
            item.setChecked(group == app.group)
            item.triggered.connect(lambda _=False, g=group: g != app.group and emit(self.name, "group_join", g))
            choice.addAction(item)
            groups.addAction(item)
        if self.groups:
            groups.addSeparator()
        groups.addAction(tr("group_new"), lambda: emit(self.name, "group_new", None))
        if app.group:
            groups.addAction(tr("group_leave"), lambda: emit(self.name, "group_leave", app.group))


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


class GroupHeader(QWidget):
    """A group's name over its tiles, with one switch for all of them. Without a name: the other apps."""

    action = Signal(str, str, object)  # group, action, argument

    def __init__(self, name=None, parent=None):
        super().__init__(parent)
        self.name = name
        self.busy = None
        self.apps = ()
        self.profiles = ()
        self.setFixedHeight(HEADER_HEIGHT)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(SIDE, 12, SIDE + 4, 4)
        layout.setSpacing(10)
        self.title = QLabel(name or tr("group_other"))
        self.title.setFont(theme.font(14, QFont.Weight.DemiBold))
        self.title.setStyleSheet(f"color: {theme.TEXT if name else theme.MUTED};")
        layout.addWidget(self.title)
        self.count = QLabel()
        self.count.setFont(theme.font(12, mono=True))
        self.count.setStyleSheet(f"color: {theme.MUTED};")
        layout.addWidget(self.count)
        layout.addStretch()
        self.switch = RouteSwitch()
        self.switch.clicked.connect(lambda checked: self.action.emit(self.name, "on" if checked else "off", None))
        self.more = IconButton("more", name or "")
        self.menu = QMenu(self.more)
        self.more.setMenu(self.menu)
        self.menu.aboutToShow.connect(self._fill_menu)
        layout.addWidget(self.switch)
        layout.addWidget(self.more)
        self.switch.setVisible(bool(name))
        self.more.setVisible(bool(name))
        self.count.setVisible(bool(name))

    def update_group(self, apps, profiles):
        self.apps, self.profiles = tuple(apps), profiles
        on = sum(1 for app in apps if app.state == "vpn")
        if not self.busy:
            self.count.setText(tr("group_count", on=on, total=len(apps)))
        self.switch.set_checked_quietly(bool(apps) and on == len(apps))
        self.switch.setToolTip(tr("group_off") if self.switch.isChecked() else tr("group_on"))

    def set_busy(self, label):
        self.busy = label
        for control in (self.switch, self.more):
            control.setEnabled(not label)
        if label:
            self.count.setText(label)
        else:
            self.update_group(self.apps, self.profiles)

    def _fill_menu(self):
        self.menu.clear()
        emit = self.action.emit
        self.menu.addAction(tr("group_on"), lambda: emit(self.name, "on", None))
        self.menu.addAction(tr("group_off"), lambda: emit(self.name, "off", None))
        self.menu.addAction(tr("group_stop"), lambda: emit(self.name, "stop", None))
        if self.profiles:
            self.menu.addSeparator()
            shared = {app.shown_profile for app in self.apps}
            add_profiles(self.menu, self.profiles, shared.pop() if len(shared) == 1 else None,
                         lambda p: emit(self.name, "switch", p))
        self.menu.addSeparator()
        self.menu.addAction(tr("group_delete"), lambda: emit(self.name, "delete", None))


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

    def resizeEvent(self, event):
        # Keep the explanation to a readable measure (about 460px) by widening the side margins.
        super().resizeEvent(event)
        side = max(32, (self.width() - 460) // 2)
        margins = self.layout().contentsMargins()
        if margins.left() != side:
            self.layout().setContentsMargins(side, margins.top(), side, margins.bottom())

    def show_message(self, title, body, button=None):
        self.title.setText(title)
        self.body.setText(body)
        self.button.setVisible(bool(button))
        if button:
            self.button.setText(button)


class MessageBar(QWidget):
    """Result line floating at the bottom; errors and offers stay until dismissed."""

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
        self.button = QPushButton()
        self.button.setFixedHeight(28)
        self.button.setStyleSheet("QPushButton { height: 28px; padding: 0 14px; border-radius: 14px; }")
        self.button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.button.hide()
        self.button.clicked.connect(self._act)
        self.callback = None
        self.close_button = IconButton("close", tr("dismiss"))
        self.close_button.setPopupMode(IconButton.ToolButtonPopupMode.DelayedPopup)
        self.close_button.clicked.connect(self.hide)
        layout.addWidget(self.dot, 0, Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self.text, 1)
        layout.addWidget(self.button, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.close_button, 0, Qt.AlignmentFlag.AlignTop)
        self.timer = QTimer(self, singleShot=True, interval=6000)
        self.timer.timeout.connect(self.hide)
        self.error = False

    def hideEvent(self, event):
        super().hideEvent(event)
        self.hidden.emit()

    def _act(self):
        callback, self.callback = self.callback, None
        self.hide()
        if callback:
            callback()

    def show_message(self, text, error, action=None, callback=None):
        """action names a button that runs callback; a message with one stays until answered."""
        self.error = error
        self.callback = callback
        self.dot.set_state(theme.DANGER if error else theme.VPN, animate=False)
        self.text.setText(text)
        self.button.setVisible(bool(action))
        if action:
            self.button.setText(action)
        self.show()
        self.shown.emit()
        self.update()
        if error or action:
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
        self.hide()  # Until there are apps to count.

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
    """Lays the tiles out in as many columns as fit, moving tiles instead of rebuilding them.

    Items are (widget, wide) pairs: a wide item (a group header) takes a
    row of its own across every column.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.grid = QGridLayout(self)
        self.base_bottom = 20 - BELOW + 8
        self.grid.setContentsMargins(20 - SIDE, 4, 20 - SIDE, self.base_bottom)
        self.grid.setSpacing(0)
        self.grid.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.items = []
        self.min_width = TILE_MIN_WIDTH
        self.columns = 0

    def set_bottom_inset(self, inset):
        """Room under the last row (for the floating message bar); tiles never move."""
        margins = self.grid.contentsMargins()
        self.grid.setContentsMargins(margins.left(), margins.top(), margins.right(), self.base_bottom + inset)

    def set_items(self, items, min_width=TILE_MIN_WIDTH):
        if items == self.items and min_width == self.min_width:
            return
        self.items = items
        self.min_width = min_width
        self.columns = 0
        self.relayout()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.relayout()

    def columns_for(self, width):
        return max(1, min(4, (width - 2 * (20 - SIDE)) // (self.min_width + 2 * SIDE)))

    def content_height(self, width):
        """The board's height at this width: what the window needs to show every tile."""
        columns, height = self.columns_for(width), 4 + self.base_bottom
        row = column = 0
        for widget, wide in self.items:
            if wide:
                height += row + widget.minimumHeight()
                row = column = 0
                continue
            row = max(row, widget.minimumHeight())
            column += 1
            if column == columns:
                height += row
                row = column = 0
        return height + row

    def relayout(self):
        columns = self.columns_for(self.width())
        if columns == self.columns and all(self.grid.indexOf(widget) >= 0 for widget, _ in self.items):
            return
        self.columns = columns
        while self.grid.count():
            self.grid.takeAt(0)
        for column in range(4):
            self.grid.setColumnStretch(column, 1 if column < columns else 0)
        row = column = 0
        for widget, wide in self.items:
            if wide:
                if column:
                    row, column = row + 1, 0
                self.grid.addWidget(widget, row, 0, 1, columns)
                row += 1
            else:
                self.grid.addWidget(widget, row, column)
                column += 1
                if column == columns:
                    row, column = row + 1, 0
            widget.show()


class Window(QWidget):
    app_action = Signal(str, str, object)
    group_action = Signal(str, str, object)
    profile_action = Signal(str, str)        # profile, action ("remove")
    setting_changed = Signal(str, object)    # key, value
    add_app = Signal()
    add_profile = Signal()
    get_engine = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("VPNGo")
        self.setWindowIcon(QIcon(str(theme.ASSETS / "vpngo.svg")))
        self.resize(760, 520)
        self.setMinimumSize(QSize(300, 360))
        self.glow = Light(self, self.update)
        self.tiles = {}
        self.headers = {}
        self.settings = {}
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        bar = QHBoxLayout()
        bar.setContentsMargins(20, 16, 14, 12)
        bar.addStrut(34)  # Same height with or without the pills, so the wordmark never moves.
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
        self.settings_button = IconButton("sliders", tr("settings"))
        self.settings_menu = QMenu(self.settings_button)
        self.settings_button.setMenu(self.settings_menu)
        self.settings_menu.aboutToShow.connect(self._fill_settings_menu)
        bar.addSpacing(2)
        bar.addWidget(self.settings_button, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(bar)

        self.board = Board()
        self.add_tile = AddTile()
        self.add_tile.clicked.connect(self.add_app)
        self.other_header = GroupHeader()
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
        self.engine_missing = False
        self._profiles = None
        self._fill_profiles_menu(())

    def _empty_action(self):
        if self.engine_missing:
            self.get_engine.emit()
        elif self.snapshot is not None and not self.snapshot.profiles:
            self.add_profile.emit()
        else:
            self.add_app.emit()

    def _fill_profiles_menu(self, profiles, manages=False):
        self.profiles_menu.clear()
        for profile in profiles:
            if manages:
                item = self.profiles_menu.addMenu(profile)
                item.menuAction().setFont(theme.font(13, mono=True))
                item.addAction(tr("remove_profile"), lambda _=False, p=profile: self.profile_action.emit(p, "remove"))
            else:
                item = self.profiles_menu.addAction(profile)
                item.setFont(theme.font(13, mono=True))
                item.setEnabled(False)
        if profiles:
            self.profiles_menu.addSeparator()
        self.profiles_menu.addAction(tr("add_profile"), self.add_profile.emit)

    def set_settings(self, settings):
        """language (None follows the system), autostart, notify, version, update (a newer version or None)."""
        self.settings = dict(settings)

    def _fill_settings_menu(self):
        menu, settings, emit = self.settings_menu, self.settings, self.setting_changed.emit
        menu.clear()
        languages = menu.addMenu(tr("language"))
        choice = QActionGroup(languages)
        for code, label in ((None, tr("language_auto")), ("pt-BR", "Português (Brasil)"), ("en-US", "English")):
            item = QAction(label, languages, checkable=True, checked=settings.get("language") == code)
            item.triggered.connect(lambda _=False, c=code: emit("language", c))
            choice.addAction(item)
            languages.addAction(item)
        for key in ("autostart", "notify"):
            item = QAction(tr(key), menu, checkable=True, checked=bool(settings.get(key)))
            item.triggered.connect(lambda on, k=key: emit(k, on))
            menu.addAction(item)
        menu.addSeparator()
        version = menu.addAction(tr("version", version=settings.get("version", "")))
        version.setEnabled(False)
        if settings.get("update"):
            menu.addAction(tr("update_to", version=settings["update"]), lambda: emit("update", True))
        elif settings.get("version") not in (None, "", "dev"):
            menu.addAction(tr("check_updates"), lambda: emit("check_updates", True))

    def show_unavailable(self, text):
        self.engine_missing = False
        self.summary.hide()
        self.profiles_button.hide()
        self.scroll.hide()
        self.empty.show_message("VPNGo", text)
        self.empty.show()

    def show_engine_missing(self, downloading=False):
        """No vpngo anywhere: offer the interface's own copy (its engine)."""
        self.engine_missing = True
        self.summary.hide()
        self.profiles_button.hide()
        self.scroll.hide()
        self.empty.show_message(tr("engine_title"), tr("engine_downloading") if downloading else tr("engine_body"),
                                tr("get_engine"))
        self.empty.button.setEnabled(not downloading)
        self.empty.show()

    def _tile(self, app):
        tile = self.tiles.get(app.name)
        if tile is None:
            tile = AppTile(app)
            tile.action.connect(self.app_action)
            self.tiles[app.name] = tile
        return tile

    def show_snapshot(self, snapshot, animate=True):
        self.engine_missing = False
        self.empty.button.setEnabled(True)
        self.profiles_button.show()
        first = self.snapshot is None
        self.snapshot = snapshot
        animate = animate and not first
        if (snapshot.profiles, snapshot.manages) != self._profiles:
            self._profiles = (snapshot.profiles, snapshot.manages)
            self._fill_profiles_menu(snapshot.profiles, snapshot.manages)
        by_name = {app.name: app for app in snapshot.apps}
        for name in list(self.tiles):
            if name not in by_name:
                self.tiles.pop(name).deleteLater()
        group_names = tuple(name for name, _ in snapshot.groups)
        items, grouped = [], set()
        for group, members in snapshot.groups:
            apps = [by_name[name] for name in members if name in by_name]
            if not apps:
                continue
            header = self.headers.get(group)
            if header is None:
                header = self.headers[group] = GroupHeader(group)
                header.action.connect(self.group_action)
            header.update_group(apps, snapshot.profiles)
            items.append((header, True))
            items += [(self._tile(app), False) for app in apps]
            grouped.update(app.name for app in apps)
        shown = {id(widget) for widget, _ in items}
        for group in list(self.headers):
            if id(self.headers[group]) not in shown:
                self.headers.pop(group).deleteLater()
        rest = [app for app in snapshot.apps if app.name not in grouped]
        if grouped and rest:
            items.append((self.other_header, True))
        items += [(self._tile(app), False) for app in rest]
        for app in snapshot.apps:
            tile = self.tiles[app.name]
            tile.update_app(app, snapshot.profiles, group_names, snapshot.platform, snapshot.manages, animate=animate)
        items.append((self.add_tile, False))
        self.other_header.setVisible(bool(grouped and rest))
        self.board.set_items(items)
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

    def fit_to_content(self):
        """Open as tall as the tiles need (within the screen), instead of a mostly empty window."""
        if self.snapshot is None or not self.snapshot.apps:
            return
        area = self.screen().availableGeometry() if self.screen() else QRectF(0, 0, 1280, 900).toRect()
        width = self.width()
        bar = 62
        height = bar + self.board.content_height(width) + 12
        self.resize(width, max(self.minimumHeight(), min(int(area.height() * .85), height)))

    def set_traffic(self, rates, history):
        for name, tile in self.tiles.items():
            tile.set_traffic(rates.get(name), history.get(name, ()))

    def set_public_ip(self, address, failed=False):
        for tile in self.tiles.values():
            tile.set_public_ip(address, failed)

    def set_busy(self, labels):
        """labels maps an app name, or "group:<name>", to the action in progress."""
        for name, tile in self.tiles.items():
            if tile.busy != labels.get(name):
                tile.set_busy(labels.get(name))
        for name, header in self.headers.items():
            if header.busy != labels.get("group:" + name):
                header.set_busy(labels.get("group:" + name))

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
