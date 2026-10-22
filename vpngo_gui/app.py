"""Wires the window, the tray and the vpngo command line together."""

import ipaddress
import os
import re
import sys
import threading
import time
import urllib.request
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QSettings, Qt, QTimer, Signal
from PySide6.QtGui import QIcon
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QDialog, QSystemTrayIcon

from . import autostart, cli, i18n, theme, updates, version
from .askpass import Broker, password_valid
from .dialogs import AddAppDialog, AddProfileDialog, ConfirmDialog, GroupDialog, PasswordDialog
from .engine import EngineError, prefix
from .i18n import tr
from .stats import Traffic
from .tray import Tray
from .window import Window


REFRESH_MS = 3000
SAVE_MS = 60_000
UPDATE_DELAY_MS = 20_000
UPDATE_EVERY = 24 * 3600
QUIET_AFTER_ACTION = 15     # Seconds in which a route change is the user's own doing, not news.
# IPv4 only: the direct route of a Linux app has no IPv6 (vpngo blocks it there), so v6 would mislead.
IP_SERVICES = ("https://api.ipify.org", "https://ipv4.icanhazip.com")
IP_KEEP = 300
MISSING = re.compile(r"(?:Required command not found|Comando necessário não encontrado): (\S+?)\.?$")
AUTH = ("Administrator authentication failed", "Falha na autenticação de administrador")
RUN = Path(__file__).resolve().parent.parent / "run.py"


def explain(error, cancelled):
    """vpngo's message, plus what to do next when the cause is a known one."""
    if cancelled or any(text in error for text in AUTH):
        return tr("hint_password")
    missing = MISSING.search(error)
    return tr("hint_missing", name=missing.group(1)) if missing else error
INSTANCE = f"vpngo-gui-{os.getuid() if hasattr(os, 'getuid') else os.environ.get('USERNAME', 'user')}"


def public_ip():
    """The address the direct route leaves from, as an outside service sees it."""
    error = None
    for url in IP_SERVICES:
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "vpngo-gui"})
            with urllib.request.urlopen(request, timeout=6) as response:
                text = response.read(64).decode("ascii", "replace").strip()
            return str(ipaddress.ip_address(text))
        except (OSError, ValueError) as failure:
            error = failure
    raise OSError(str(getattr(error, "reason", error)))


class Results(QObject):
    snapshot = Signal(object, object)          # Snapshot or None, error text or None
    finished = Signal(object, str, object)     # busy keys, action text, (token, error text or None, success text)
    engine = Signal(object)                    # error text or None
    public_ip = Signal(object, object)         # address or None, error text or None
    update_found = Signal(object, object, bool)  # newer version or None, error text or None, asked by the user
    updated = Signal(object)                   # error text or None


class Controller(QObject):
    def __init__(self, application):
        super().__init__()
        self.application = application
        self.settings = QSettings("vpngo-gui", "settings")
        i18n.OVERRIDE = self.settings.value("language") or None
        self.tray = Tray(self) if QSystemTrayIcon.isSystemTrayAvailable() else None
        self.broker = Broker(self._ask_password) if os.name != "nt" else None
        self.results = Results()
        self.results.snapshot.connect(self._snapshot)
        self.results.finished.connect(self._finished)
        self.results.engine.connect(self._engine_ready)
        self.results.public_ip.connect(self._public_ip)
        self.results.update_found.connect(self._update_found)
        self.results.updated.connect(self._updated)
        self.downloading = False
        self.busy = {}
        self.acted = {}
        self.ip = None            # (address, monotonic time) of the last lookup.
        self.looking_up = False
        self.newer = None
        self.updating = False
        self.traffic = Traffic()
        self.history_path = prefix() / "state/history.json"
        self.traffic.load(self.history_path)
        self.current = None
        self.refreshing = False
        self.pending_show = False
        self.shown = False        # Save the window's size only once it has been seen.
        self.window = self._make_window()
        geometry = self.settings.value("geometry")
        self.placed = bool(geometry) and self.window.restoreGeometry(geometry)
        if self.tray:
            self.tray.app_action.connect(self.act)
            self.tray.group_action.connect(self.group_act)
            self.tray.open_window.connect(self.toggle_window)
            self.tray.quit.connect(self.quit)
            self.tray.show()
        self.timer = QTimer(self, interval=REFRESH_MS)
        self.timer.timeout.connect(self.refresh)
        self.timer.start()
        self.save_timer = QTimer(self, interval=SAVE_MS)
        self.save_timer.timeout.connect(lambda: self.traffic.save(self.history_path))
        self.save_timer.start()
        QTimer.singleShot(UPDATE_DELAY_MS, lambda: self.check_updates(manual=False))
        self.refresh()

    def _make_window(self):
        window = Window()
        window.keep_in_tray = self.tray is not None
        window.app_action.connect(self.act)
        window.group_action.connect(self.group_act)
        window.profile_action.connect(self.profile_act)
        window.setting_changed.connect(self.change_setting)
        window.add_app.connect(self.add_app)
        window.add_profile.connect(self.add_profile)
        window.get_engine.connect(self.get_engine)
        window.set_settings(self._settings())
        return window

    def _settings(self):
        try:
            starts = autostart.enabled()
        except OSError:
            starts = False
        return {"language": i18n.OVERRIDE, "autostart": starts, "notify": self._notify(),
                "version": version(), "update": self.newer}

    def _notify(self):
        return str(self.settings.value("notify", "true")).lower() == "true"

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
            self._show_if_pending()
            return
        previous, self.current = self.current, snapshot
        rates = self.traffic.update(snapshot.apps)
        self.window.show_snapshot(snapshot)
        self.window.set_traffic(rates, self.traffic.history)
        self.window.set_busy(self.busy)
        if self.tray:
            self.tray.show_snapshot(snapshot, self.busy)
        if previous is not None:
            self._notify_changes(previous, snapshot)
        self._show_if_pending()

    def _notify_changes(self, previous, snapshot):
        """Tell the user when an app leaves the VPN without having asked for it."""
        if not self.tray or not self._notify():
            return
        before = {app.name: app.state for app in previous.apps}
        now = time.monotonic()
        for app in snapshot.apps:
            if before.get(app.name) != "vpn" or app.state == "vpn" or app.name in self.busy:
                continue
            if now - self.acted.get(app.name, -QUIET_AFTER_ACTION) < QUIET_AFTER_ACTION:
                continue
            text = (tr("app_closed", app=app.name) if app.state == "stopped" else
                    tr("left_vpn", app=app.name, state=tr("state_" + app.state)))
            self.tray.showMessage("VPNGo", text, QSystemTrayIcon.MessageIcon.Warning, 8000)

    # --- Actions ---------------------------------------------------------------

    def act(self, name, action, argument):
        if action == "lookup":
            return self.lookup_ip()
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
        elif action == "group_new":
            return self.edit_group(None, checked=(name,))
        elif action == "group_join":
            text, label, steps = tr("action_group_add", app=name, group=argument), tr("busy_save"), [
                ["group", "add", argument, name]]
        elif action == "group_leave":
            text, label, steps = tr("action_group_leave", app=name, group=argument), tr("busy_save"), [
                ["group", "remove", argument, name]]
        elif action == "policy":
            policy, on = argument
            text, label, steps = tr("action_policy", app=name), tr("busy_save"), [
                ["policy", name, policy, "on" if on else "off"]]
        elif action == "remove":
            dialog = ConfirmDialog(tr("remove_title", app=name), tr("remove_body"), tr("remove"), self.window)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            text, label, steps = tr("action_remove", app=name), tr("busy_remove"), [["app", "remove", name]]
        else:
            text = tr({"start": "action_start", "stop": "action_stop", "on": "action_on",
                       "off": "action_off"}[action], app=name)
            label = tr("busy_" + action)
            steps = [[action, name]]
        self.run(name, text, steps, label)

    def group_act(self, group, action, argument):
        if self.current is None:
            return
        if action in {"new", "edit"}:
            return self.edit_group(group or None)
        members = next((list(apps) for name, apps in self.current.groups if name == group), [])
        keys = ["group:" + group, *members]
        if any(key in self.busy for key in keys):
            return
        if action == "delete":
            return self.run(keys[:1], tr("action_group_delete", group=group), [["group", "remove", group]],
                            tr("busy_save"))
        if action == "switch":
            return self.run(keys, tr("action_group_switch", group=group, profile=argument),
                            [["group", "switch", group, argument]], tr("busy_switch", profile=argument))
        # One vpngo command for the whole group: one password, and vpngo carries on past a failing app.
        self.run(keys, tr("action_group_" + action, group=group), [["group", action, group]],
                 tr("busy_" + action), timeout=120 * max(1, len(members)))

    def edit_group(self, group, checked=()):
        """Create a group (group None) or change one's name and apps, in a single vpngo action."""
        if self.current is None or (group and "group:" + group in self.busy):
            return
        apps = [(app.name, app.group) for app in self.current.apps]
        dialog = GroupDialog(apps, (name for name, _ in self.current.groups), group, checked, self.window)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        name, chosen = dialog.values()
        before = next((list(members) for g, members in self.current.groups if g == group), [])
        steps = []
        if group and name != group:
            steps.append(["group", "rename", group, name])
        added = [app for app in chosen if app not in before]
        removed = [app for app in before if app not in chosen]
        # Add before removing: a group emptied on the way would be deleted.
        if added:
            steps.append(["group", "add", name, *added])
        if removed:
            steps.append(["group", "remove", name, *removed])
        if not steps:
            return
        keys = ["group:" + (group or name), *dict.fromkeys(before + added)]
        text = tr("action_group_edit" if group else "action_group_new", group=name)
        self.run(keys, text, steps, tr("busy_save"))

    def profile_act(self, profile, action):
        if action == "remove":
            self.run("profile:" + profile, tr("action_remove_profile", profile=profile),
                     [["profile", "remove", profile]])

    def run(self, names, text, steps, label=None, timeout=120, success=None):
        """Run vpngo steps in a thread; names are the busy keys (apps, "group:<name>") meanwhile."""
        names = [names] if isinstance(names, str) else list(names)
        for name in names:
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
            self.results.finished.emit(names, text, (token, error, success))
        threading.Thread(target=work, daemon=True).start()

    def _finished(self, names, text, outcome):
        token, error, success = outcome
        cancelled = bool(self.broker and token and self.broker.end(token))
        now = time.monotonic()
        for name in names:
            self.busy.pop(name, None)
            self.acted[name] = now
        self._show_busy()
        if error:
            error = explain(error, cancelled)
            self.window.message.show_message(tr("failed", action=text, error=error), error=True)
            if self.tray and not self.window.isVisible():
                self.tray.showMessage("VPNGo", tr("failed", action=text, error=error),
                                      QSystemTrayIcon.MessageIcon.Warning, 8000)
        elif success:
            self.window.message.show_message(success, error=False)
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
        path, name, profile, start, once = dialog.values()
        if once:
            # Windows runs vpngo.ps1 directly, which takes the form vpngo.cmd translates --temp into.
            step = ["temp", profile, path, "detach"] if os.name == "nt" else ["--temp", profile, path, "-d"]
            return self.run("temp:" + name, tr("action_temp", app=name), [step],
                            success=tr("temp_started", app=name))
        steps = [["config", path], ["assign", name, profile]] + ([["start", name]] if start else [])
        self.run(name, tr("action_add_app", app=name), steps)

    def add_profile(self):
        dialog = AddProfileDialog(self.current.profiles if self.current else (), self.window)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        name, path = dialog.values()
        self.run(f"profile:{name}", tr("action_add_profile", profile=name), [["profile", "add", name, path]])

    def lookup_ip(self):
        """Look the public IP up once for every direct tile, and reuse it for a few minutes."""
        if self.ip and time.monotonic() - self.ip[1] < IP_KEEP:
            return self.window.set_public_ip(self.ip[0])
        if self.looking_up:
            return
        self.looking_up = True

        def work():
            try:
                self.results.public_ip.emit(public_ip(), None)
            except OSError as error:
                self.results.public_ip.emit(None, str(error))
        threading.Thread(target=work, daemon=True).start()

    def _public_ip(self, address, error):
        self.looking_up = False
        if address:
            self.ip = (address, time.monotonic())
            self.window.set_public_ip(address)
        else:
            self.window.set_public_ip(None, failed=True)
            self.window.message.show_message(tr("public_failed", error=error), error=True)

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

    # --- Settings and updates --------------------------------------------------

    def change_setting(self, key, value):
        if key == "language":
            self.set_language(value)
        elif key == "autostart":
            try:
                autostart.set_enabled(bool(value))
            except OSError as error:
                self.window.message.show_message(str(error), error=True)
        elif key == "notify":
            self.settings.setValue("notify", "true" if value else "false")
        elif key == "update":
            self.start_update()
        elif key == "check_updates":
            self.check_updates(manual=True)
        self.window.set_settings(self._settings())

    def set_language(self, code):
        """Rebuild the window in the new language; the tray menu follows on its next build."""
        if code == i18n.OVERRIDE:
            return
        i18n.OVERRIDE = code
        if code:
            self.settings.setValue("language", code)
        else:
            self.settings.remove("language")
        old = self.window
        self.window = self._make_window()
        self.window.setGeometry(old.geometry())
        if self.current is not None:
            self.window.show_snapshot(self.current, animate=False)
            self.window.set_traffic({}, self.traffic.history)
            self.window.set_busy(self.busy)
        if old.isVisible():
            self.window.show()
        old.keep_in_tray = False
        old.close()
        old.deleteLater()
        if self.tray and self.current:
            self.tray.show_snapshot(self.current, self.busy)
        self.window.message.show_message(tr("language_changed"), error=False)

    def check_updates(self, manual):
        if version() == "dev" or self.updating:
            return
        last = float(self.settings.value("update_checked", 0) or 0)
        if not manual and time.time() - last < UPDATE_EVERY:
            return
        if manual:
            self.window.message.show_message(tr("checking"), error=False)

        def work():
            try:
                self.results.update_found.emit(updates.check(), None, manual)
            except (EngineError, OSError, ValueError) as error:
                self.results.update_found.emit(None, str(error), manual)
        threading.Thread(target=work, daemon=True).start()

    def _update_found(self, available, error, manual):
        if error:
            if manual:
                self.window.message.show_message(tr("failed", action=tr("check_updates"), error=error), error=True)
            return
        self.settings.setValue("update_checked", time.time())
        self.newer = available
        self.window.set_settings(self._settings())
        if available:
            self.window.message.show_message(tr("update_available", version=available), error=False,
                                             action=tr("update"), callback=self.start_update)
        elif manual:
            self.window.message.show_message(tr("up_to_date"), error=False)

    def start_update(self):
        if self.updating or not self.newer:
            return
        self.updating = True
        self.window.message.show_message(tr("action_update") + "…", error=False)

        def work():
            try:
                updates.update()
                self.results.updated.emit(None)
            except (cli.CommandError, EngineError, OSError) as error:
                self.results.updated.emit(str(error))
        threading.Thread(target=work, daemon=True).start()

    def _updated(self, error):
        self.updating = False
        if error:
            self.window.message.show_message(tr("failed", action=tr("action_update"), error=error), error=True)
            return
        installed, self.newer = self.newer, None
        self.window.set_settings(self._settings())
        self.window.message.show_message(tr("updated", version=installed), error=False,
                                         action=tr("reopen"), callback=self.restart)

    def restart(self):
        """Start the newly installed interface, which waits for this one to quit."""
        if QProcess.startDetached(sys.executable, [str(RUN), "--replace"]):
            self.quit()

    # --- Window ----------------------------------------------------------------

    def show_when_ready(self):
        """Show the window after the first answer from vpngo, sized to it; never wait more than a moment."""
        self.pending_show = True
        QTimer.singleShot(1500, self._show_if_pending)

    def _show_if_pending(self):
        if not self.pending_show:
            return
        self.pending_show = False
        if not self.placed:
            self.window.fit_to_content()
        self.show_window()

    def show_window(self):
        self.shown = True
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
        self.save_timer.stop()
        self.traffic.save(self.history_path)
        if self.shown:
            self.settings.setValue("geometry", self.window.saveGeometry())
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


def instance_running():
    socket = QLocalSocket()
    socket.connectToServer(INSTANCE)
    return socket.waitForConnected(300)


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


def main(hidden=False, replace=False):
    application = QApplication(sys.argv[:1])
    application.setApplicationName("vpngo-gui")
    application.setApplicationDisplayName("VPNGo")
    application.setDesktopFileName("vpngo-gui")
    application.setQuitOnLastWindowClosed(False)
    if replace:
        # Restarting after an update: the old instance is on its way out.
        deadline = time.monotonic() + 10
        while instance_running() and time.monotonic() < deadline:
            time.sleep(.2)
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
        controller.show_when_ready()
    application.aboutToQuit.connect(controller.shutdown)
    if controller.tray is None:
        application.setQuitOnLastWindowClosed(True)
    code = application.exec()
    server.close()
    return code
