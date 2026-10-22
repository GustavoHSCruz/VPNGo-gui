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

DEMO = {
    "profiles": ["br", "us"],
    "apps": [
        {"name": "vesktop", "profile": "us", "state": "vpn", "active_profile": "us"},
        {"name": "firefox", "profile": "br", "state": "vpn", "active_profile": "br"},
        {"name": "steam", "profile": "us", "state": "direct", "active_profile": "us"},
        {"name": "spotify", "profile": "us", "state": "stopped", "active_profile": None},
    ],
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
    print(f"Saved screenshots in {out}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".impeccable/review")
