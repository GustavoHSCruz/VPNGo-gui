"""Parsing, command building, the askpass handshake and the window, against a fake vpngo."""

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["VPNGO_LANG"] = "en-US"

from vpngo_gui import cli
from vpngo_gui.i18n import MESSAGES

try:
    from PySide6.QtCore import QEventLoop, QTimer
    from PySide6.QtWidgets import QApplication
except ImportError:  # The pure-Python parts still run without PySide6.
    QApplication = None

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

    def controller(self):
        from vpngo_gui.app import Controller
        application = QApplication.instance() or QApplication([])
        controller = Controller(application)
        controller.timer.stop()
        self.addCleanup(lambda: controller.broker and controller.broker.close())
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


if __name__ == "__main__":
    unittest.main()
