# Product

<!-- impeccable:product-schema 1 -->

## Platform

desktop (Qt via PySide6; Linux first, also macOS and Windows). None of web/ios/android/adaptive applies.

## Stack

Python 3 + PySide6 (Qt Widgets). Chosen because vpngo itself is Python, Qt looks native on all three systems vpngo supports, and PySide6 is LGPL (compatible with Apache-2.0).

## Users

People who already use the vpngo command line and want to route individual desktop apps (a chat client, a browser, a game) through different WireGuard exits without opening a terminal each time. The owner uses it daily on CachyOS + Hyprland, in Portuguese (pt-BR).

## Product Purpose

A graphical front end for the vpngo CLI. It shows which managed apps are running, through which VPN profile, and whether each app is on the VPN or on the direct route, and lets the user start, stop, toggle and switch apps, and register profiles and apps, without a terminal.

Success: the everyday loop (open the app on the VPN, check it is on the VPN, flip it off/on or to another exit) takes one or two clicks from the tray.

## Positioning

Per-application routing: each app gets its own exit, and the rest of the system stays on the normal connection. The GUI never re-implements routing; it drives the same `vpngo` commands, so the CLI stays the single source of truth.

## Operating Context

- Lives in the system tray; the window is opened briefly and closed again.
- State comes from `vpngo status --json`, which needs no administrator password, and is refreshed periodically.
- Actions run `vpngo` commands. On Linux and macOS some ask for the sudo password; the GUI asks for it in its own dialog (sudo askpass). On Windows, Windows itself shows the UAC prompt.
- Installed by `vpngo --install-gui`, or without vpngo by this project's `install.py`, which uses a compatible vpngo on PATH or downloads vpngo as the interface's private engine (not on PATH). Either way the release is verified and installed in a private virtual environment.

## Capabilities and Constraints

v1 scope (confirmed):
- Per app: status (stopped, on VPN, direct, partial), start, stop, VPN on/off, switch profile.
- Per running app (asked for on 2026-10-22): running time, download/upload rate with a short traffic trace, and the VPN server address masked until clicked. On Linux the traffic is the app's namespace veth (VPN-encrypted bytes when on the VPN); on macOS and Windows it is the total of the app's open Mihomo connections.
- Register a VPN profile from a WireGuard `.conf`, and register an app by executable.
- Tray icon with quick actions per app; closing the window keeps the tray.
- Language: pt-BR and English, following the system language and `VPNGO_LANG`, like the CLI.

- Asked for on 2026-10-22 (second round): time on the current route and on each route in total instead of time since the app opened; the traffic trace coloured by route; the public IP on the direct route (looked up only on click); a detail view so one or two apps do not leave the window bare; groups that turn several apps on or off at once; each app's own icon; removing apps and profiles; kill switch and DNS policy (Linux); running a program once ("só desta vez"); start with the system; a notice when an app leaves the VPN on its own; update checks; choosing the language.
- The app icon is the owner's vpngo mark from the owner's GitHub profile: a dot splitting into a green (VPN), an amber and a dotted grey (direct) path.

Out of scope (stay in the CLI): helpers and Windows `shutdown`.

Terms come from the CLI: profile, app, start, stop, on, off, switch.

## Brand Commitments

- Name: VPNGo (`vpngo` for the command).
- Visual base made binding by the user: the owner's local search site in `~/searxng/site` (dark warm neutrals, Inter + JetBrains Mono, a single "connection color" that carries the current route state).

## Evidence on Hand

The app mark `vpngo_gui/assets/vpngo.svg` (two routes from one point, the lit one green) was authored for this interface. Screenshots in `.impeccable/review/` use synthetic demo data, except `real.png`. Do not invent usage numbers or testimonials.

## Product Principles

1. The route state is the product: whether an app is on the VPN must be readable at a glance.
2. The CLI is the source of truth; the GUI never guesses a state it cannot read.
3. Minimal options: anything rare stays in the CLI.
4. Never surprise with privileges: say why a password is requested, and ask once per action.
