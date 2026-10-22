"""Parsing, command building, the askpass handshake and the window, against a fake vpngo."""

import atexit
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["VPNGO_LANG"] = "en-US"
# Settings, saved history and the autostart entry go to a throwaway home, never the real one.
SANDBOX = tempfile.mkdtemp(prefix="vpngo-gui-test-")
os.environ.update(XDG_CONFIG_HOME=str(Path(SANDBOX) / "config"), VPNGO_GUI_PREFIX=str(Path(SANDBOX) / "gui"),
                  APPDATA=str(Path(SANDBOX) / "appdata"), LOCALAPPDATA=str(Path(SANDBOX) / "local"))

from vpngo_gui import cli
from vpngo_gui.i18n import MESSAGES

try:
    from PySide6.QtCore import QEventLoop, QTimer
    from PySide6.QtWidgets import QApplication
except ImportError:  # The pure-Python parts still run without PySide6.
    QApplication = None

atexit.register(shutil.rmtree, SANDBOX, ignore_errors=True)

FAKE = [sys.executable, str(ROOT / "tests/fake_vpngo.py")]
DEMO = {
    "profiles": ["br", "us"],
    "apps": [
        {"name": "vesktop", "profile": "us", "state": "vpn", "active_profile": "us"},
        {"name": "steam", "profile": "us", "state": "direct", "active_profile": "us"},
        {"name": "spotify", "profile": "br", "state": "stopped", "active_profile": None},
    ],
}


class FakeCli(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.state = Path(self.directory.name) / "state.json"
        self.state.write_text(json.dumps(DEMO))
        self.environment = {"FAKE_VPNGO_STATE": str(self.state), "VPNGO_GUI_CLI": json.dumps(FAKE)}
        self.saved = {name: os.environ.get(name) for name in self.environment}
        os.environ.update(self.environment)

    def tearDown(self):
        for name, value in self.saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        self.directory.cleanup()

    def log(self):
        return [entry for entry in json.loads(self.state.read_text()).get("log", []) if entry[0] != "status"]


class CliTest(FakeCli):
    def test_snapshot_reads_profiles_apps_and_counts_vpn(self):
        snapshot = cli.snapshot()
        self.assertEqual(snapshot.profiles, ("br", "us"))
        self.assertEqual([app.name for app in snapshot.apps], ["vesktop", "steam", "spotify"])
        self.assertEqual(snapshot.on_vpn, 1)
        self.assertFalse(snapshot.apps[2].running)

    def test_unknown_state_is_shown_as_partial_and_old_format_is_refused(self):
        snapshot = cli.parse_snapshot(json.dumps({"schema": 1, "profiles": [], "apps": [
            {"name": "x", "profile": "us", "state": "weird"}]}))
        self.assertEqual(snapshot.apps[0].state, "partial")
        with self.assertRaises(ValueError):
            cli.parse_snapshot(json.dumps({"profiles": [], "apps": []}))

    def test_errors_carry_vpngos_own_message(self):
        data = json.loads(self.state.read_text())
        data["fail"] = "Profile 'zz' was not found."
        self.state.write_text(json.dumps(data))
        with self.assertRaisesRegex(cli.CommandError, "^Profile 'zz' was not found.$"):
            cli.run(["start", "steam"])

    def test_missing_vpngo_is_reported(self):
        os.environ["VPNGO_GUI_CLI"] = json.dumps(["/nonexistent/vpngo"])
        with self.assertRaisesRegex(cli.CommandError, "vpngo-missing"):
            cli.run(["status", "--json"])

    def test_commands_have_no_terminal(self):
        if os.name == "nt":
            self.skipTest("POSIX sessions only")
        script = Path(self.directory.name) / "tty.sh"
        script.write_text("#!/bin/sh\nif [ -t 0 ] || (: </dev/tty) 2>/dev/null; then echo tty; else echo none; fi\n")
        script.chmod(0o755)
        os.environ["VPNGO_GUI_CLI"] = json.dumps([str(script)])
        self.assertEqual(cli.run(["x"]).strip(), "none")


class StatsTest(unittest.TestCase):
    def app(self, rx, tx, state="vpn"):
        return cli.App(name="vesktop", profile="us", state=state, rx_bytes=rx, tx_bytes=tx)

    def test_rates_come_from_counter_deltas_and_skip_a_sample_when_counters_drop(self):
        from vpngo_gui.stats import Traffic
        traffic = Traffic()
        self.assertEqual(traffic.update([self.app(1000, 100)], now=0), {})
        self.assertEqual(traffic.update([self.app(7000, 400)], now=3), {"vesktop": (2000.0, 100.0)})
        self.assertEqual(list(traffic.history["vesktop"]), [(2100.0, "vpn")])
        self.assertEqual(traffic.update([self.app(10, 5, "direct")], now=6), {})
        self.assertEqual(traffic.update([self.app(310, 5, "direct")], now=9), {"vesktop": (100.0, 0.0)})
        self.assertEqual(list(traffic.history["vesktop"]), [(2100.0, "vpn"), (100.0, "direct")])
        traffic.update([self.app(None, None, "stopped")], now=12)
        self.assertNotIn("vesktop", traffic.history)

    def test_history_survives_a_quick_restart_only(self):
        from vpngo_gui import stats
        traffic = stats.Traffic()
        traffic.history["vesktop"] = stats.deque([(5.0, "vpn"), (7.0, "direct")])
        path = Path(SANDBOX) / "history.json"
        traffic.save(path)
        again = stats.Traffic()
        again.load(path)
        self.assertEqual(list(again.history["vesktop"]), [(5.0, "vpn"), (7.0, "direct")])
        with patch.object(stats.time, "time", return_value=time.time() + stats.RESUME + 5):
            stale = stats.Traffic()
            stale.load(path)
        self.assertEqual(stale.history, {})

    def test_two_clocks_one_per_route(self):
        from vpngo_gui.stats import short_duration
        from vpngo_gui.window import route_clocks, route_tip
        now = time.time()
        app = cli.App(name="vesktop", profile="us", state="direct", started_at=now - 16 * 3600,
                      route_since=now - 10 * 60, vpn_seconds=15 * 3600 + 50 * 60, direct_seconds=600)
        self.assertEqual(route_clocks(app), (("vpn", 15 * 3600 + 50 * 60), ("direct", 600)))
        tip = route_tip(app)
        self.assertIn("Direct for 10 min", tip)
        self.assertIn("Open for 16 h 00 min", tip)
        self.assertEqual([short_duration(v) for v in (20, 27 * 60, 15 * 3600 + 46 * 60, 2 * 86400 + 3 * 3600)],
                         ["0m", "27m", "15h46", "2d3h"])
        older = cli.App(name="x", profile="us", state="vpn", started_at=now - 60)
        self.assertEqual([route for route, _ in route_clocks(older)], ["vpn"])

    def test_readable_rates_uptime_and_masked_addresses(self):
        from vpngo_gui.stats import masked, rate_text, split_endpoint, uptime_text
        self.assertEqual([rate_text(v) for v in (0, 950, 48_000, 1_240_000)], ["0 B/s", "950 B/s", "48 kB/s", "1.2 MB/s"])
        self.assertEqual(uptime_text(1000, now=1000 + 23 * 60), "23 min")
        self.assertEqual(uptime_text(0.0), "")
        self.assertEqual(uptime_text(1000, now=1000 + 4 * 3600 + 59 * 60), "4 h 59 min")
        self.assertEqual(uptime_text(1000, now=1000 + 2 * 86400 + 3 * 3600), "2 d 3 h")
        self.assertEqual(split_endpoint("146.70.230.82:51820"), ("146.70.230.82", "51820"))
        self.assertEqual(split_endpoint("[2001:db8::1]:51820"), ("2001:db8::1", "51820"))
        self.assertEqual(masked("146.70.230.82"), "146.70.•••.•••")
        self.assertEqual(masked("2001:db8::1"), "2001:db8:•••")
        self.assertNotIn("230", masked("146.70.230.82"))


class TranslationTest(unittest.TestCase):
    def test_both_languages_have_the_same_messages(self):
        self.assertEqual(set(MESSAGES["en-US"]), set(MESSAGES["pt-BR"]))


@unittest.skipIf(QApplication is None, "PySide6 is not installed")
class AskpassTest(unittest.TestCase):
    def test_one_password_answers_every_request_of_an_action_then_is_forgotten(self):
        from vpngo_gui.askpass import Broker
        application = QApplication.instance() or QApplication([])
        asked = []
        broker = Broker(lambda text: asked.append(text) or "s3cret")
        try:
            token, environment = broker.begin("Starting steam")
            env = {**os.environ, **environment, "PYTHONPATH": str(ROOT)}

            def ask():
                process = subprocess.Popen([environment["SUDO_ASKPASS"], "[sudo] password:"], env=env,
                                           stdout=subprocess.PIPE, text=True)
                deadline = time.monotonic() + 10
                while process.poll() is None and time.monotonic() < deadline:
                    application.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 50)
                output = process.communicate()[0]
                return process.returncode, output

            self.assertEqual(ask(), (0, "s3cret\n"))
            self.assertEqual(ask(), (0, "s3cret\n"))
            self.assertEqual(asked, ["Starting steam"])
            broker.end(token)
            self.assertEqual(ask()[0], 1)
        finally:
            broker.close()

    def test_cancel_cancels_the_whole_action(self):
        from vpngo_gui.askpass import Broker
        application = QApplication.instance() or QApplication([])
        asked = []
        broker = Broker(lambda text: asked.append(text) and None)
        try:
            token, environment = broker.begin("Stopping steam")
            env = {**os.environ, **environment, "PYTHONPATH": str(ROOT)}
            for _ in range(2):
                process = subprocess.Popen([environment["SUDO_ASKPASS"], "p"], env=env, stdout=subprocess.PIPE)
                while process.poll() is None:
                    application.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 50)
                process.communicate()
                self.assertEqual(process.returncode, 1)
            self.assertEqual(len(asked), 1)
        finally:
            broker.close()


@unittest.skipIf(QApplication is None, "PySide6 is not installed")
class WindowTest(FakeCli):
    def settle(self, until, timeout=10):
        deadline = time.monotonic() + timeout
        while not until() and time.monotonic() < deadline:
            loop = QEventLoop()
            QTimer.singleShot(30, loop.quit)
            loop.exec()
        self.assertTrue(until())

    def drain(self):
        from PySide6.QtCore import QCoreApplication, QEvent
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        QCoreApplication.processEvents()

    def controller(self):
        from vpngo_gui.app import Controller
        application = QApplication.instance() or QApplication([])
        controller = Controller(application)
        controller.timer.stop()
        self.addCleanup(self.drain)
        self.addCleanup(controller.shutdown)
        self.settle(lambda: controller.current is not None)
        return controller

    def test_tiles_follow_state_and_keep_their_widgets_across_refreshes(self):
        controller = self.controller()
        tiles = dict(controller.window.tiles)
        self.assertEqual(set(tiles), {"vesktop", "steam", "spotify"})
        self.assertTrue(tiles["vesktop"].switch.isChecked())
        self.assertFalse(tiles["steam"].switch.isChecked())
        self.assertTrue(tiles["spotify"].switch.isHidden())
        controller.refresh()
        self.settle(lambda: not controller.refreshing)
        self.assertEqual(controller.window.tiles, tiles)

    def test_without_vpngo_the_window_offers_its_own_engine(self):
        from vpngo_gui import engine
        os.environ.pop("VPNGO_GUI_CLI")
        prefix = Path(self.directory.name) / "gui"
        with (patch.dict(os.environ, {"VPNGO_GUI_PREFIX": str(prefix)}),
              patch.object(cli.shutil, "which", return_value=None),
              patch.object(engine, "download_engine", return_value=FAKE)):
            from vpngo_gui.app import Controller
            application = QApplication.instance() or QApplication([])
            controller = Controller(application)
            controller.timer.stop()
            self.addCleanup(self.drain)
            self.addCleanup(controller.shutdown)
            self.settle(lambda: controller.window.engine_missing)
            self.assertFalse(controller.window.empty.button.isHidden())
            controller.window.empty.button.click()
            self.settle(lambda: controller.current is not None)
        self.assertEqual(json.loads((prefix / "cli.json").read_text())["command"], FAKE)
        self.assertEqual(set(controller.window.tiles), {"vesktop", "steam", "spotify"})

    def test_server_address_is_masked_until_clicked(self):
        data = json.loads(self.state.read_text())
        data["apps"][0]["endpoint"] = "146.70.230.82:51820"
        self.state.write_text(json.dumps(data))
        controller = self.controller()
        server = controller.window.tiles["vesktop"].server
        self.assertEqual(server.text(), "146.70.•••.•••")
        server.toggle()
        self.assertEqual(server.text(), "146.70.230.82")
        controller.refresh()
        self.settle(lambda: not controller.refreshing)
        self.assertEqual(server.text(), "146.70.230.82")  # A refresh keeps the user's choice.
        server.toggle()
        self.assertEqual(server.text(), "146.70.•••.•••")
        self.assertEqual(controller.window.tiles["spotify"].server.text(), "")

    def test_window_opens_as_tall_as_its_tiles(self):
        data = json.loads(self.state.read_text())
        data["apps"] = data["apps"][:1]
        self.state.write_text(json.dumps(data))
        controller = self.controller()
        controller.window.resize(760, 900)
        controller.window.fit_to_content()
        self.assertLess(controller.window.height(), 400)

    def test_groups_gather_tiles_and_act_as_one(self):
        data = json.loads(self.state.read_text())
        data["groups"] = {"games": ["steam", "spotify"]}
        self.state.write_text(json.dumps(data))
        controller = self.controller()
        window = controller.window
        header = window.headers["games"]
        self.assertEqual(header.count.text(), "0 of 2 on VPN")
        self.assertFalse(window.other_header.isHidden())
        order = [widget for widget, _ in window.board.items]
        self.assertEqual(order[:4], [header, window.tiles["steam"], window.tiles["spotify"], window.other_header])
        header.switch.click()
        self.settle(lambda: not controller.busy)
        self.settle(lambda: header.count.text() == "2 of 2 on VPN")
        controller.act("vesktop", "group_join", "games")
        self.settle(lambda: not controller.busy)
        controller.group_act("games", "switch", "br")
        self.settle(lambda: not controller.busy)
        self.assertEqual(self.log(), [["group", "on", "games"], ["group", "add", "games", "vesktop"],
                                      ["group", "switch", "games", "br"]])
        self.settle(lambda: window.other_header.isHidden())

    def test_groups_are_created_and_edited_from_one_dialog(self):
        from vpngo_gui import dialogs
        data = json.loads(self.state.read_text())
        data["groups"] = {"games": ["steam", "spotify"]}
        self.state.write_text(json.dumps(data))
        controller = self.controller()
        self.assertFalse(controller.window.groups_button.isHidden())
        dialog = dialogs.GroupDialog([("vesktop", None), ("steam", "games")], ["games"], checked=("vesktop",))
        self.assertEqual(dialog.values(), ("", ["vesktop"]))
        dialog.submit()
        self.assertIn("letter", dialog.error.text())
        self.assertIn("in games", dialog.boxes[1].text())

        def answer(name, apps):
            def exec_(dialog):
                dialog.name.setText(name)
                for box in dialog.boxes:
                    box.setChecked(box.property("app") in apps)
                return dialogs.QDialog.DialogCode.Accepted
            return exec_
        with patch.object(dialogs.GroupDialog, "exec", answer("chat", ["vesktop"])):
            controller.group_act("", "new", None)
        self.settle(lambda: not controller.busy)
        with patch.object(dialogs.GroupDialog, "exec", answer("play", ["steam", "vesktop"])):
            controller.group_act("games", "edit", None)
        self.settle(lambda: not controller.busy)
        self.assertEqual(self.log(), [["group", "add", "chat", "vesktop"], ["group", "rename", "games", "play"],
                                      ["group", "add", "play", "vesktop"], ["group", "remove", "play", "spotify"]])

    def test_protection_and_removal_reach_vpngo(self):
        from vpngo_gui import dialogs
        controller = self.controller()
        controller.act("steam", "policy", ("dns", True))
        self.settle(lambda: not controller.busy)
        with patch.object(dialogs.ConfirmDialog, "exec", return_value=dialogs.QDialog.DialogCode.Accepted):
            controller.act("spotify", "remove", None)
        self.settle(lambda: not controller.busy)
        controller.profile_act("br", "remove")
        self.settle(lambda: not controller.busy)
        self.assertEqual(self.log(), [["policy", "steam", "dns", "on"], ["app", "remove", "spotify"],
                                      ["profile", "remove", "br"]])
        self.settle(lambda: "spotify" not in controller.window.tiles)

    def test_direct_tiles_look_up_the_public_ip_only_when_asked(self):
        from vpngo_gui import app as app_module
        controller = self.controller()
        server = controller.window.tiles["steam"].server
        self.assertEqual(server.text(), "•••.•••.•••.•••")
        with patch.object(app_module, "public_ip", return_value="203.0.113.7") as lookup:
            server.toggle()
            self.settle(lambda: server.text() == "203.0.113.7")
            server.toggle()
            self.assertEqual(server.text(), "203.0.•••.•••")
        lookup.assert_called_once()

    def test_an_unexpected_exit_from_the_vpn_is_announced(self):
        controller = self.controller()
        shown = []
        controller.tray = type("Tray", (), {"showMessage": lambda self, *a: shown.append(a[1]),
                                            "show_snapshot": lambda self, *a: None, "hide": lambda self: None,
                                            "setContextMenu": lambda self, m: None, "deleteLater": lambda self: None,
                                            "menu": type("M", (), {"deleteLater": lambda self: None})()})()
        data = json.loads(self.state.read_text())
        data["apps"][0]["state"] = "direct"
        self.state.write_text(json.dumps(data))
        controller.refresh()
        self.settle(lambda: shown)
        self.assertEqual(shown, ["vesktop left the VPN: now direct."])

    def test_language_can_be_chosen_in_the_window(self):
        from vpngo_gui import i18n
        controller = self.controller()
        self.addCleanup(setattr, i18n, "OVERRIDE", None)
        old = controller.window
        controller.change_setting("language", "pt-BR")
        self.assertIsNot(controller.window, old)
        self.assertEqual(controller.window.summary.label.text(), "1 de 3 na VPN")
        self.assertEqual(set(controller.window.tiles), {"vesktop", "steam", "spotify"})
        controller.change_setting("language", None)

    def test_autostart_entry_runs_this_interface_hidden(self):
        from vpngo_gui import autostart
        autostart.set_enabled(True)
        self.assertTrue(autostart.enabled())
        text = autostart.linux_entry().read_text()
        self.assertIn("run.py --hidden", text)
        autostart.set_enabled(False)
        self.assertFalse(autostart.enabled())

    def test_actions_run_the_matching_vpngo_commands(self):
        controller = self.controller()
        for name, action, argument in (("steam", "on", None), ("vesktop", "profile", "br"),
                                       ("spotify", "profile", "us"), ("spotify", "start", None)):
            controller.act(name, action, argument)
            self.settle(lambda: not controller.busy)
            self.settle(lambda: not controller.refreshing)
        self.assertEqual(self.log(), [["on", "steam"], ["switch", "vesktop", "br"],
                                      ["assign", "spotify", "us"], ["start", "spotify"]])

    def test_switching_a_direct_app_turns_the_vpn_on_first(self):
        controller = self.controller()
        controller.act("steam", "profile", "br")
        self.settle(lambda: not controller.busy)
        self.assertEqual(self.log(), [["on", "steam"], ["switch", "steam", "br"]])

    def test_failure_shows_vpngos_message(self):
        controller = self.controller()
        data = json.loads(self.state.read_text())
        data["fail"] = "vopono is not installed."
        self.state.write_text(json.dumps(data))
        controller.act("steam", "on", None)
        self.settle(lambda: not controller.busy)
        self.assertTrue(controller.window.message.isVisibleTo(controller.window))
        self.assertIn("vopono is not installed.", controller.window.message.text.text())

    def test_dialogs_open_and_validate(self):
        from vpngo_gui.dialogs import AddAppDialog, AddProfileDialog
        app_dialog = AddAppDialog(["br", "us"])
        app_dialog.path.setText("/nonexistent/thing")
        app_dialog.submit()
        self.assertTrue(app_dialog.error.isVisibleTo(app_dialog))
        app_dialog.path.setText(sys.executable)
        app_dialog.profile.setCurrentText("us")
        app_dialog.submit()
        self.assertEqual(app_dialog.result(), app_dialog.DialogCode.Accepted)
        self.assertEqual(app_dialog.values()[2], "us")
        app_dialog.once.setChecked(True)
        self.assertFalse(app_dialog.start_now.isEnabled())
        self.assertTrue(app_dialog.values()[4])
        profile_dialog = AddProfileDialog(["us"])
        conf = Path(self.directory.name) / "US.conf"
        conf.write_text("[Interface]\n")
        profile_dialog.path.setText(str(conf))
        self.assertEqual(profile_dialog.name.text(), "us")
        profile_dialog.submit()
        self.assertIn("exists", profile_dialog.error.text())

    def test_new_app_path_maps_to_vpngos_app_name(self):
        from vpngo_gui.dialogs import app_key, profile_from_file
        self.assertEqual(app_key("/usr/bin/Vesktop"), "vesktop")
        self.assertEqual(app_key("C:/Games/Steam.exe"), "steam")
        self.assertIsNone(app_key("/tmp/$weird"))
        self.assertEqual(profile_from_file("/x/US-Free 82.conf"), "us-free-82")
        self.assertEqual(profile_from_file("/x/01-br.conf"), "br")



def tearDownModule():
    # Destroy every Qt wrapper while the QApplication still exists; PySide can crash if
    # Python's interpreter shutdown deletes them in arbitrary order afterwards.
    if QApplication is None or QApplication.instance() is None:
        return
    import gc
    from PySide6.QtCore import QCoreApplication, QEvent
    for widget in QApplication.topLevelWidgets():
        widget.close()
        widget.deleteLater()
    for _ in range(3):
        gc.collect()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        QCoreApplication.processEvents()


if __name__ == "__main__":
    unittest.main()
