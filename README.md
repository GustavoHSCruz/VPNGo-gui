# VPNGo interface

A tray app and window for [vpngo](https://github.com/GustavoHSCruz/VPNGo), the launcher that routes individual apps through WireGuard. Each app is a tile lit by its route: green on the VPN, unlit on the direct route, hollow when stopped.

A running app's tile also shows how long it has been on its current route (and, when it fits, its total on the other one), its download and upload rates over a faint trace that is green where traffic went through the VPN and grey where it went direct, and an address masked until you click it: the VPN server's, or on the direct route your public IP, looked up only when you click. Each app shows its own icon. Its tooltip adds the total on each route and the data moved since the last switch.

From the window or the tray you can:

- start, restart and stop an app, or a whole group;
- switch an app (or a group) between the VPN and the direct route;
- change the VPN profile an app or a group uses;
- put apps in groups, which appear as headings with one switch for all their apps;
- set an app's kill switch and DNS isolation (Linux; they apply on its next start);
- add and remove VPN profiles (WireGuard `.conf` files) and apps, or run a program on the VPN just this once.

The settings button chooses the language, starts the interface with the system (in the tray), turns on a notice when an app leaves the VPN without you asking, and checks for updates. The interface runs the same `vpngo` commands you would type, so the command line stays the source of truth. Helpers and the Windows `shutdown` command stay in the command line.

## Install

**Without vpngo installed.** Download `install.py` from the [latest release](https://github.com/GustavoHSCruz/VPNGo-gui/releases/latest) and run it with Python 3:

```sh
curl -fLO https://github.com/GustavoHSCruz/VPNGo-gui/releases/latest/download/install.py
python3 install.py          # Windows: python install.py
```

It looks for `vpngo` on `PATH` first. If it finds vpngo 0.5.0 or newer, the interface uses it. If not (missing, or too old), it downloads the latest vpngo release, checks it against `SHA256SUMS` and keeps it as the interface's own engine in its folder, without adding a `vpngo` command. Either way that vpngo then installs the interface. vpngo's system requirements still apply: on Linux, vopono and the tools listed in the [vpngo guide](https://github.com/GustavoHSCruz/VPNGo/blob/main/docs/HOWTO.md).

**With vpngo installed** (0.5.0 or newer; 0.7.0 or newer for groups, time per route and removing apps and profiles):

```sh
vpngo --install-gui
```

Both download the latest interface release, check it against `SHA256SUMS`, and install it with its own Python environment, so PySide6 (Qt) never touches your system Python. The first install downloads about 250 MB; a PySide6 already installed on the system (for example the distribution's package) is reused. Run the same command again to upgrade.

If the window opens and finds no vpngo at all, it offers to download its engine itself. `vpngo-gui --update-engine` updates a downloaded engine to the latest vpngo. Once a day the interface checks for a newer release and offers to update; the update also refreshes its engine, then asks to reopen.

| System | Installed in | Command | Menu entry |
| --- | --- | --- | --- |
| Linux | `~/.local/share/vpngo-gui` | `~/.local/bin/vpngo-gui` | yes |
| macOS | `~/.local/share/vpngo-gui` | `~/.local/bin/vpngo-gui` | no |
| Windows | `%LOCALAPPDATA%\vpngo-gui` | `%USERPROFILE%\bin\vpngo-gui.cmd` | no |

`vpngo-gui --hidden` starts in the tray without opening the window. Closing the window keeps the tray running; use **Quit** in the tray menu to exit. Opening it again while it runs shows the existing window.

To remove it, turn off **Start with the system** in its settings, then delete the install folder (it also holds the downloaded engine, if any), its settings (`~/.config/vpngo-gui`; on Windows, the registry key `HKCU\Software\vpngo-gui`), the command and, on Linux, `~/.local/share/applications/vpngo-gui.desktop`.

## Passwords

On Linux and macOS, starting, stopping and switching apps needs administrator rights, and vpngo asks sudo for them. The interface shows its own password dialog, names the action that needs it, checks the password with sudo, and uses it only until that action finishes. On Windows, Windows shows its usual permission prompt.

## Language

Text follows the language chosen in the settings button; on **Automatic**, `VPNGO_LANG` and otherwise the system language: Brazilian Portuguese (`pt-BR`) or English.

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
