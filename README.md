# VPNGo interface

A tray app and window for [vpngo](https://github.com/GustavoHSCruz/VPNGo), the launcher that routes individual apps through WireGuard. Each app is a tile lit by its route: green on the VPN, unlit on the direct route, hollow when stopped.

From the window or the tray you can:

- start, restart and stop an app;
- switch an app between the VPN and the direct route;
- change the VPN profile an app uses;
- add a VPN profile (a WireGuard `.conf`) and add an app.

The interface runs the same `vpngo` commands you would type, so the command line stays the source of truth. Kill switch and DNS policies, helpers, temporary runs and the Windows `shutdown` command stay in the command line.

## Install

Install vpngo 0.5.0 or newer first, then run:

```sh
vpngo --install-gui
```

The command downloads the latest interface release, checks it against `SHA256SUMS`, and installs it with its own Python environment, so PySide6 (Qt) never touches your system Python. The first install downloads about 250 MB; a PySide6 already installed on the system (for example the distribution's package) is reused. Run it again to upgrade.

| System | Installed in | Command | Menu entry |
| --- | --- | --- | --- |
| Linux | `~/.local/share/vpngo-gui` | `~/.local/bin/vpngo-gui` | yes |
| macOS | `~/.local/share/vpngo-gui` | `~/.local/bin/vpngo-gui` | no |
| Windows | `%LOCALAPPDATA%\vpngo-gui` | `%USERPROFILE%\bin\vpngo-gui.cmd` | no |

`vpngo-gui --hidden` starts in the tray without opening the window. Closing the window keeps the tray running; use **Quit** in the tray menu to exit. Opening it again while it runs shows the existing window.

To remove it, delete the install folder, the command and, on Linux, `~/.local/share/applications/vpngo-gui.desktop`.

## Passwords

On Linux and macOS, starting, stopping and switching apps needs administrator rights, and vpngo asks sudo for them. The interface shows its own password dialog, names the action that needs it, checks the password with sudo, and uses it only until that action finishes. On Windows, Windows shows its usual permission prompt.

## Language

Text follows `VPNGO_LANG` and otherwise the system language: Brazilian Portuguese (`pt-BR`) or English.

## Development

```sh
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
VPNGO_GUI_CLI=/path/to/VPNGo/linux/vpngo .venv/bin/python run.py
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests
QT_QPA_PLATFORM=offscreen .venv/bin/python tools/screenshot.py .impeccable/review
```

`VPNGO_GUI_CLI` picks the vpngo to drive (a path, or a JSON list for a command with arguments); without it the interface uses the one recorded by `vpngo --install-gui`, then `vpngo` on `PATH`. The tests and `tools/screenshot.py` use `tests/fake_vpngo.py`, so they never touch a real VPN. The screenshot data is synthetic.

To release, run `tools/tag-release.sh 1.2.3`: it tests, builds and pushes the tag; the Release workflow publishes `vpngo-gui-1.2.3.tar.gz` and `SHA256SUMS`.

## License

Apache License 2.0. The bundled Inter and JetBrains Mono fonts are under the SIL Open Font License 1.1 (`vpngo_gui/assets/fonts/OFL.txt`).
