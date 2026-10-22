"""Wires the window, the tray and the vpngo command line together."""

import os
import re
import sys
import threading

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QIcon
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QDialog, QSystemTrayIcon

from . import cli, theme
from .askpass import Broker, password_valid
from .dialogs import AddAppDialog, AddProfileDialog, PasswordDialog
from .i18n import tr
from .stats import Traffic
from .tray import Tray
from .window import Window


REFRESH_MS = 3000
MISSING = re.compile(r"(?:Required command not found|Comando necessário não encontrado): (\S+?)\.?$")
AUTH = ("Administrator authentication failed", "Falha na autenticação de administrador")


def explain(error, cancelled):
    """vpngo's message, plus what to do next when the cause is a known one."""
    if cancelled or any(text in error for text in AUTH):
        return tr("hint_password")
    missing = MISSING.search(error)
    return tr("hint_missing", name=missing.group(1)) if missing else error
INSTANCE = f"vpngo-gui-{os.getuid() if hasattr(os, 'getuid') else os.environ.get('USERNAME', 'user')}"


class Results(QObject):
    snapshot = Signal(object, object)          # Snapshot or None, error text or None
    finished = Signal(str, str, object)        # app name, action text, error text or None
    engine = Signal(object)                    # error text or None


class Controller(QObject):
    def __init__(self, application):
        super().__init__()
        self.application = application
        self.window = Window()
        self.tray = Tray(self) if QSystemTrayIcon.isSystemTrayAvailable() else None
        self.window.keep_in_tray = self.tray is not None
        self.broker = Broker(self._ask_password) if os.name != "nt" else None
        self.results = Results()
        self.results.snapshot.connect(self._snapshot)
        self.results.finished.connect(self._finished)
        self.results.engine.connect(self._engine_ready)
        self.downloading = False
        self.busy = {}
        self.traffic = Traffic()
        self.current = None
        self.refreshing = False
        self.window.app_action.connect(self.act)
        self.window.add_app.connect(self.add_app)
        self.window.add_profile.connect(self.add_profile)
        self.window.get_engine.connect(self.get_engine)
        if self.tray:
            self.tray.app_action.connect(self.act)
            self.tray.open_window.connect(self.toggle_window)
            self.tray.quit.connect(self.quit)
            self.tray.show()
        self.timer = QTimer(self, interval=REFRESH_MS)
        self.timer.timeout.connect(self.refresh)
        self.timer.start()
        self.refresh()

    # --- State -----------------------------------------------------------------

    def refresh(self):
        if self.refreshing:
            return
        self.refreshing = True

        def work():
            try:
                self.results.snapshot.emit(cli.snapshot(), None)
            except (cli.CommandError, ValueError, KeyError) as error:
                self.results.snapshot.emit(None, str(error))
        threading.Thread(target=work, daemon=True).start()

    def _snapshot(self, snapshot, error):
        self.refreshing = False
        if snapshot is None:
            if error == "vpngo-missing":
                self.window.show_engine_missing(self.downloading)
            elif not self.downloading:
                self.window.show_unavailable(error)
            return
        self.current = snapshot
        rates = self.traffic.update(snapshot.apps)
        self.window.show_snapshot(snapshot)
        self.window.set_traffic(rates, self.traffic.history)
        self.window.set_busy(self.busy)
        if self.tray:
            self.tray.show_snapshot(snapshot, self.busy)

    # --- Actions ---------------------------------------------------------------

    def act(self, name, action, argument):
        if name in self.busy or self.current is None:
            return
        app = next((item for item in self.current.apps if item.name == name), None)
        if app is None:
            return
        if action == "profile":
            if argument == app.shown_profile:
                return
            text = tr("action_switch", app=name, profile=argument)
            label = tr("busy_switch", profile=argument)
            if not app.running:
                steps = [["assign", name, argument]]
            elif app.state == "vpn":
                steps = [["switch", name, argument]]
            else:  # Both backends switch only a route that is on the VPN.
                steps = [["on", name], ["switch", name, argument]]
        else:
            text = tr({"start": "action_start", "stop": "action_stop", "on": "action_on",
                       "off": "action_off"}[action], app=name)
            label = tr("busy_" + action)
            steps = [[action, name]]
        self.run(name, text, steps, label)

    def run(self, name, text, steps, label=None, timeout=120):
        self.busy[name] = label or tr("busy_add")
        self._show_busy()
        token, environment = self.broker.begin(text) if self.broker else (None, {})

        def work():
            error = None
            try:
                for step in steps:
                    cli.run(step, environment, timeout=timeout)
            except cli.CommandError as failure:
                error = tr("cli_missing") if str(failure) == "vpngo-missing" else str(failure)
            self.results.finished.emit(name, text, (token, error))
        threading.Thread(target=work, daemon=True).start()

    def _finished(self, name, text, outcome):
        token, error = outcome
        cancelled = bool(self.broker and token and self.broker.end(token))
        self.busy.pop(name, None)
        self._show_busy()
        if error:
            error = explain(error, cancelled)
            self.window.message.show_message(tr("failed", action=text, error=error), error=True)
            if self.tray and not self.window.isVisible():
                self.tray.showMessage("VPNGo", tr("failed", action=text, error=error),
                                      QSystemTrayIcon.MessageIcon.Warning, 8000)
        self.refreshing = False
        self.refresh()

    def _show_busy(self):
        self.window.set_busy(self.busy)
        if self.tray and self.current:
            self.tray.show_snapshot(self.current, self.busy)

    def add_app(self):
        if not self.current or not self.current.profiles:
            return self.add_profile()
        dialog = AddAppDialog(self.current.profiles, self.window)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        path, name, profile, start = dialog.values()
        steps = [["config", path], ["assign", name, profile]] + ([["start", name]] if start else [])
        self.run(name, tr("action_add_app", app=name), steps)

    def add_profile(self):
        dialog = AddProfileDialog(self.current.profiles if self.current else (), self.window)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        name, path = dialog.values()
        self.run(f"profile:{name}", tr("action_add_profile", profile=name), [["profile", "add", name, path]])

    def get_engine(self):
        """Download vpngo as the interface's private engine and start using it."""
        if self.downloading:
            return
        self.downloading = True
        self.window.show_engine_missing(downloading=True)

        def work():
            from . import engine
            try:
                engine.record(engine.download_engine(report=lambda message: None))
                self.results.engine.emit(None)
            except (engine.EngineError, OSError) as error:
                self.results.engine.emit(str(error))
        threading.Thread(target=work, daemon=True).start()

    def _engine_ready(self, error):
        self.downloading = False
        if error:
            self.window.show_engine_missing()
            self.window.message.show_message(tr("failed", action=tr("get_engine"), error=error), error=True)
        self.refreshing = False
        self.refresh()

    def _ask_password(self, action_text):
        self.show_window()
        dialog = PasswordDialog(action_text, password_valid, self.window)
        dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
        return dialog.result_password if dialog.exec() == QDialog.DialogCode.Accepted else None

    # --- Window ----------------------------------------------------------------

    def show_window(self):
        self.window.show()
        self.window.raise_()
        self.window.activateWindow()

    def toggle_window(self):
        if self.window.isVisible() and self.window.isActiveWindow():
            self.window.hide()
        else:
            self.show_window()

    def shutdown(self):
        """Tear Qt objects down in order; leaving it to interpreter exit can crash in Qt's destructors."""
        self.timer.stop()
        # Work still running in threads must not reach widgets that are about to be deleted.
        self.results.blockSignals(True)
        if self.broker:
            self.broker.close()
            self.broker = None
        if self.tray:
            self.tray.hide()
            self.tray.setContextMenu(None)
            self.tray.menu.deleteLater()
            self.tray.deleteLater()
            self.tray = None
        self.window.keep_in_tray = False
        self.window.close()
        self.window.deleteLater()

    def quit(self):
        self.application.quit()


def already_running():
    """Hand over to a running instance: it shows its window, this one exits."""
    socket = QLocalSocket()
    socket.connectToServer(INSTANCE)
    if socket.waitForConnected(300):
        socket.write(b"show\n")
        socket.flush()
        socket.waitForBytesWritten(300)
        return True
    return False


def main(hidden=False):
    application = QApplication(sys.argv[:1])
    application.setApplicationName("vpngo-gui")
    application.setApplicationDisplayName("VPNGo")
    application.setDesktopFileName("vpngo-gui")
    application.setQuitOnLastWindowClosed(False)
    if already_running():
        return 0
    application.setStyle("Fusion")
    theme.load_fonts()
    application.setFont(theme.font(14))
    application.setPalette(theme.palette())
    application.setStyleSheet(theme.STYLE)
    application.setWindowIcon(QIcon(str(theme.ASSETS / "vpngo.svg")))
    QLocalServer.removeServer(INSTANCE)
    server = QLocalServer()
    server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
    server.listen(INSTANCE)
    controller = Controller(application)
    server.newConnection.connect(lambda: (server.nextPendingConnection(), controller.show_window()))
    if not hidden or controller.tray is None:
        controller.show_window()
    application.aboutToQuit.connect(controller.shutdown)
    if controller.tray is None:
        application.setQuitOnLastWindowClosed(True)
    code = application.exec()
    server.close()
    return code
