#!/usr/bin/env python3
"""Render the window offscreen with demo data (synthetic) and save PNGs for review.

    QT_QPA_PLATFORM=offscreen python tools/screenshot.py <out-dir>
"""

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import math
import time

NOW = time.time()
DEMO = {
    "profiles": ["br", "us"],
    "apps": [
        {"name": "vesktop", "profile": "us", "state": "vpn", "active_profile": "us",
         "started_at": NOW - 4 * 3600 - 59 * 60, "endpoint": "146.70.230.82:51820",
         "route_since": NOW - 4 * 3600 - 59 * 60, "vpn_seconds": 4 * 3600 + 59 * 60, "direct_seconds": 0},
        {"name": "firefox", "profile": "br", "state": "vpn", "active_profile": "br",
         "started_at": NOW - 23 * 60, "endpoint": "185.159.157.13:51820",
         "route_since": NOW - 8 * 60, "vpn_seconds": 8 * 60, "direct_seconds": 15 * 60},
        {"name": "steam", "profile": "us", "state": "direct", "active_profile": "us",
         "started_at": NOW - 2 * 86400 - 3 * 3600, "endpoint": "146.70.230.82:51820",
         "route_since": NOW - 40 * 60, "vpn_seconds": 2 * 86400 + 2 * 3600, "direct_seconds": 40 * 60},
        {"name": "spotify", "profile": "us", "state": "stopped", "active_profile": None},
    ],
}


def trace(rate, count=40, direct_from=None, direct_until=None):
    """Synthetic samples; the stretch between direct_from and direct_until went direct."""
    return [(rate(i), "direct" if direct_from is not None and direct_from <= i < (direct_until or count) else "vpn")
            for i in range(count)]


# Synthetic traffic (bytes per second) for the screenshots only.
TRAFFIC = {
    "vesktop": ((48_000, 9_500), trace(lambda i: 30_000 + 25_000 * abs(math.sin(i / 4)))),
    "firefox": ((1_240_000, 61_000), trace(lambda i: 200_000 + 900_000 * max(0, math.sin(i / 6)) ** 2,
                                           direct_from=6, direct_until=22)),
    "steam": ((3_200, 800), trace(lambda i: 9_000 + 6_500 * abs(math.sin(i / 3)), direct_from=14)),
}


def main(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    state = Path(tempfile.mkdtemp()) / "state.json"
    os.environ["FAKE_VPNGO_STATE"] = str(state)
    os.environ["VPNGO_GUI_CLI"] = json.dumps([sys.executable, str(ROOT / "tests/fake_vpngo.py")])
    from PySide6.QtCore import QEventLoop, QTimer
    from PySide6.QtWidgets import QApplication
    from vpngo_gui import app as gui
    from vpngo_gui.cli import parse_snapshot

    application = QApplication([])
    gui.theme.load_fonts()
    application.setStyle("Fusion")
    application.setFont(gui.theme.font(14))
    application.setPalette(gui.theme.palette())
    application.setStyleSheet(gui.theme.STYLE)

    def settle(ms=900):
        loop = QEventLoop()
        QTimer.singleShot(ms, loop.quit)
        loop.exec()

    def shot(name, data, size=(760, 520), busy=(), message=None):
        state.write_text(json.dumps(data))
        window = gui.Window()
        window.resize(*size)
        window.show()
        snapshot = parse_snapshot(json.dumps({"schema": 1, **data}))
        window.show_snapshot(snapshot, animate=False)
        window.set_traffic({name: rates for name, (rates, _) in TRAFFIC.items()},
                           {name: history for name, (_, history) in TRAFFIC.items()})
        window.set_busy(dict(busy))
        if message:
            window.message.show_message(*message)
        settle()
        window.grab().save(str(out / f"{name}.png"))
        window.close()

    from vpngo_gui.app import explain
    from vpngo_gui.i18n import tr
    shot("board", DEMO)
    from vpngo_gui.app import explain
    from vpngo_gui.i18n import tr
    shot("board-busy", DEMO, busy={"steam": tr("busy_on")},
         message=(tr("failed", action=tr("action_on", app="firefox"),
                     error=explain("Comando necessário não encontrado: vopono.", False)), True))
    partial = json.loads(json.dumps(DEMO))
    partial["apps"][2]["state"] = "partial"
    shot("partial", partial)
    shot("narrow", DEMO, size=(380, 640))
    shot("narrow-error", DEMO, size=(380, 640),
         message=(tr("failed", action=tr("action_on", app="steam"), error=explain("Falha na autenticação de administrador.", False)), True))
    shot("wide", DEMO, size=(1100, 560))
    shot("empty", {"profiles": ["us"], "apps": []})

    # The shortest trace that is drawn (6 quiet samples), and a long name in the narrowest tiles.
    saved = dict(TRAFFIC)
    TRAFFIC.clear()
    TRAFFIC["vesktop"] = ((900, 300), trace(lambda i: 1_000 + 300 * (i % 3), 6))
    shot("warmup", {"profiles": ["us"], "apps": [DEMO["apps"][0]]})
    TRAFFIC.clear()
    TRAFFIC["telegram-desktop"] = ((1_240_000, 61_000), saved["firefox"][1])
    long_name = {**DEMO["apps"][1], "name": "telegram-desktop"}
    worst = {**DEMO["apps"][0], "started_at": NOW - 23 * 3600 - 59 * 60}
    TRAFFIC["vesktop"] = ((899_000, 99_000), saved["firefox"][1])
    shot("long-name", {"profiles": ["br", "us"], "apps": [long_name, worst, DEMO["apps"][2]]},
         size=(700, 520))
    TRAFFIC.clear()
    TRAFFIC.update(saved)

    # A revealed address in the narrowest tiles.
    state.write_text(json.dumps(DEMO))
    narrow = gui.Window()
    narrow.resize(700, 520)
    narrow.show()
    narrow.show_snapshot(parse_snapshot(json.dumps({"schema": 1, **DEMO})), animate=False)
    narrow.set_traffic({name: rates for name, (rates, _) in TRAFFIC.items()},
                       {name: history for name, (_, history) in TRAFFIC.items()})
    narrow.tiles["firefox"].server.toggle()
    settle()
    narrow.grab().save(str(out / "narrow-ip-shown.png"))
    narrow.close()

    from vpngo_gui.dialogs import AddAppDialog, AddProfileDialog, PasswordDialog
    for name, dialog in (("dialog-add-app", AddAppDialog(["br", "us"])), ("dialog-add-profile", AddProfileDialog()),
                         ("dialog-password", PasswordDialog("Iniciar steam pela VPN", lambda value: False))):
        dialog.show()
        settle(300)
        dialog.grab().save(str(out / f"{name}.png"))
        dialog.close()

    state.write_text(json.dumps(DEMO))
    window = gui.Window()
    window.resize(760, 520)
    window.show()
    window.show_snapshot(parse_snapshot(json.dumps({"schema": 1, **DEMO})), animate=False)
    window.set_traffic({name: rates for name, (rates, _) in TRAFFIC.items()},
                       {name: history for name, (_, history) in TRAFFIC.items()})
    window.tiles["firefox"].server.toggle()
    settle()
    window.grab().save(str(out / "board-ip-shown.png"))
    tile = window.tiles["vesktop"]
    tile._fill_menu()
    tile.menu.popup(tile.more.mapToGlobal(tile.more.rect().bottomLeft()))
    settle(300)
    tile.menu.grab().save(str(out / "tile-menu.png"))
    tile.menu.close()

    from vpngo_gui.tray import Tray
    tray = Tray()
    tray.show_snapshot(parse_snapshot(json.dumps({"schema": 1, **DEMO})), {"steam": tr("busy_on")})
    tray.menu.popup(window.mapToGlobal(window.rect().center()))
    settle(300)
    tray.menu.grab().save(str(out / "tray-menu.png"))
    first = tray.menu.actions()[0].menu()
    first.popup(window.mapToGlobal(window.rect().center()))
    settle(300)
    first.grab().save(str(out / "tray-app-menu.png"))
    shot("no-profiles", {"profiles": [], "apps": []})

    # Few apps: the detail view. First the case that prompted it: one app, on the direct route.
    TRAFFIC.clear()
    TRAFFIC["vesktop"] = ((286, 176), trace(lambda i: 600 + 9_000 * max(0, math.sin(i / 9)) ** 8 + 300 * (i % 3),
                                            200, direct_from=150))
    single = {**DEMO["apps"][0], "state": "direct", "route_since": NOW - 10 * 60,
              "vpn_seconds": 15 * 3600 + 36 * 60, "direct_seconds": 10 * 60,
              "route_rx_bytes": 38_949_877, "route_tx_bytes": 2_140_000}
    one = gui.Window()
    one.resize(1100, 520)
    one.show()
    one.show_snapshot(parse_snapshot(json.dumps({"schema": 1, "profiles": ["br", "us"], "apps": [single],
                                                 "groups": []})), animate=False)
    one.set_traffic({"vesktop": TRAFFIC["vesktop"][0]}, {"vesktop": TRAFFIC["vesktop"][1]})
    one.fit_to_content()
    settle()
    one.grab().save(str(out / "detail-one.png"))
    one.tiles["vesktop"].set_public_ip("203.0.113.7")
    one.tiles["vesktop"].server.toggle()
    settle(200)
    one.grab().save(str(out / "detail-one-ip.png"))
    one.close()
    TRAFFIC["firefox"] = ((1_240_000, 61_000), trace(lambda i: 200_000 + 900_000 * max(0, math.sin(i / 14)) ** 2,
                                                     200, direct_from=60, direct_until=120))
    two = {"profiles": ["br", "us"], "apps": [{**single, "route_since": NOW - 10 * 60}, {
        **DEMO["apps"][1], "route_rx_bytes": 410_000_000, "route_tx_bytes": 12_500_000}], "groups": []}
    pair = gui.Window()
    pair.resize(760, 520)
    pair.show()
    pair.show_snapshot(parse_snapshot(json.dumps({"schema": 1, **two})), animate=False)
    pair.set_traffic({name: rates for name, (rates, _) in TRAFFIC.items()},
                     {name: history for name, (_, history) in TRAFFIC.items()})
    pair.fit_to_content()
    settle()
    pair.grab().save(str(out / "detail-two.png"))
    pair.close()
    TRAFFIC.clear()
    TRAFFIC.update(saved)

    # Groups.
    grouped = {**DEMO, "groups": [{"name": "jogos", "apps": ["steam", "spotify"]}]}
    for app in grouped["apps"]:
        app["group"] = "jogos" if app["name"] in ("steam", "spotify") else None
    shot("groups", grouped, size=(760, 760))
    shot("groups-busy", grouped, size=(760, 760), busy={"group:jogos": tr("busy_on"), "steam": tr("busy_on"),
                                                         "spotify": tr("busy_on")})
    board = gui.Window()
    board.resize(760, 760)
    board.show()
    board.show_snapshot(parse_snapshot(json.dumps({"schema": 1, **grouped})), animate=False)
    board.set_settings({"language": None, "autostart": True, "notify": True, "version": "0.3.0", "update": "0.4.0"})
    settle(300)
    board._fill_settings_menu()
    board.settings_menu.popup(board.settings_button.mapToGlobal(board.settings_button.rect().bottomLeft()))
    settle(300)
    board.settings_menu.grab().save(str(out / "settings-menu.png"))
    board.settings_menu.close()
    tile = board.tiles["steam"]
    tile._fill_menu()
    tile.menu.popup(tile.more.mapToGlobal(tile.more.rect().bottomLeft()))
    settle(300)
    tile.menu.grab().save(str(out / "tile-menu-full.png"))
    tile.menu.close()
    board.message.show_message(tr("update_available", version="0.4.0"), False, tr("update"), lambda: None)
    settle(300)
    board.grab().save(str(out / "update-offer.png"))
    board.close()
    from vpngo_gui.dialogs import ConfirmDialog, GroupDialog
    for name, dialog in (("dialog-group", GroupDialog("steam")),
                         ("dialog-remove", ConfirmDialog(tr("remove_title", app="spotify"), tr("remove_body"),
                                                         tr("remove")))):
        dialog.show()
        settle(300)
        dialog.grab().save(str(out / f"{name}.png"))
        dialog.close()
    lonely = gui.Window()
    lonely.resize(760, 520)
    lonely.show()
    lonely.show_engine_missing()
    settle(300)
    lonely.grab().save(str(out / "engine-missing.png"))
    lonely.close()
    print(f"Saved screenshots in {out}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".impeccable/review")
