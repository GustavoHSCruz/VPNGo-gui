"""Tray icon with quick actions per app."""

from PySide6.QtCore import QByteArray, QRectF, Qt, Signal
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from . import theme
from .i18n import tr
from .stats import uptime_text
from .window import add_profiles


def tray_icon(on):
    """The app mark, its route lit only while some app is on the VPN."""
    svg = (theme.ASSETS / "vpngo.svg").read_text(encoding="utf-8")
    if not on:
        svg = svg.replace(theme.VPN, theme.MUTED)
    renderer = QSvgRenderer(QByteArray(svg.encode()))
    result = QIcon()
    for size in (16, 22, 24, 32, 48, 64):
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        renderer.render(painter, QRectF(0, 0, size, size))
        painter.end()
        result.addPixmap(pixmap)
    return result


class Tray(QSystemTrayIcon):
    app_action = Signal(str, str, object)
    open_window = Signal()
    quit = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.icons = {True: tray_icon(True), False: tray_icon(False)}
        self.setIcon(self.icons[False])
        self.menu = QMenu()
        self.setContextMenu(self.menu)
        self.menu.aboutToHide.connect(self._apply_pending)
        self.activated.connect(self._activated)
        self.snapshot = None
        self.busy = set()
        self.pending = False
        self._build()

    def _activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self.open_window.emit()

    def show_snapshot(self, snapshot, busy):
        self.snapshot, self.busy = snapshot, dict(busy)
        on = snapshot.on_vpn if snapshot else 0
        self.setIcon(self.icons[bool(on)])
        summary = tr("summary", on=on, total=len(snapshot.apps)) if on else tr("summary_none")
        self.setToolTip(tr("tray_tooltip", summary=summary))
        # Never rebuild a menu the user is reading; catch up when it closes.
        if self.menu.isVisible():
            self.pending = True
        else:
            self._build()

    def _apply_pending(self):
        if self.pending:
            self.pending = False
            self._build()

    def _build(self):
        self.menu.clear()
        snapshot = self.snapshot
        if snapshot is not None:
            for app in snapshot.apps:
                self.menu.addMenu(self._app_menu(app, snapshot.profiles))
            if snapshot.apps:
                self.menu.addSeparator()
        self.menu.addAction(tr("open"), self.open_window.emit)
        self.menu.addAction(tr("quit"), self.quit.emit)

    def _app_menu(self, app, profiles):
        state = f"{app.shown_profile} · {self.busy.get(app.name) or tr('state_' + app.state)}"
        if app.running and app.started_at and app.name not in self.busy:
            state += f" · {uptime_text(app.started_at)}"
        menu = QMenu(f"{app.name}    {state}", self.menu)
        menu.setEnabled(app.name not in self.busy)
        emit = self.app_action.emit
        if app.running:
            if app.state == "vpn":
                menu.addAction(tr("vpn_off"), lambda: emit(app.name, "off", None))
            else:
                menu.addAction(tr("vpn_on"), lambda: emit(app.name, "on", None))
            menu.addAction(tr("restart"), lambda: emit(app.name, "start", None))
            menu.addAction(tr("stop"), lambda: emit(app.name, "stop", None))
        else:
            menu.addAction(tr("start"), lambda: emit(app.name, "start", None))
        if len(profiles) > 1:
            menu.addSeparator()
            add_profiles(menu, profiles, app.shown_profile, lambda p: emit(app.name, "profile", p))
        return menu
