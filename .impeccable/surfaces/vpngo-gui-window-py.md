---
version: 1
slug: "vpngo-gui-window-py"
primary_target: "vpngo_gui/window.py"
related_targets: ["vpngo_gui/tray.py"]
---

# VPNGo main window and tray

Scope: the desktop window (vpngo_gui/window.py) and the tray menu (vpngo_gui/tray.py). Mode: Operate.

Task: see at a glance which apps are on the VPN, flip one between VPN and direct, start/stop it, switch its profile, add a profile (.conf) or an app (executable). Opened briefly from the tray, several times a day.

Constraints: state comes from `vpngo status --json` every few seconds; actions run vpngo commands that may ask for the sudo password (Linux/macOS) through the app's own dialog. Refresh must never move or rebuild a tile under the pointer or a focused control.

## Direction contract

THESIS: The route is the light. Every app is a tile lit by its route: lit green on the VPN, unlit on the direct route, dark and hollow when stopped. It refuses the settings-table arrangement (rows of names with a status column).

OWN-WORLD: the ~/searxng site: ground #111113, surface #19191c, hairline #26262a, text #e9e7e2, muted #8b8984, connection green #4cc38a; Inter for UI, JetBrains Mono only for profile names and endpoints (data); 14px tile radius, inset top highlight, soft long shadow; a faint radial glow at the top of the window in the color of the overall state.

STORY: the user opens the window, reads the tile colors before any word, flips a switch or starts an app, and closes the window; the tray remembers everything.

FIRST VIEWPORT: 760x520 default. Top bar: "VPNGo" wordmark left, a pill on the right with the state dot and "2 de 3 na VPN". Below, a 3-column grid of 168px tiles: state dot top-left, overflow menu top-right, app name 20px semibold, then profile in mono with the VPN switch at the bottom right; stopped tiles show "Iniciar" instead of the switch. Last cell: dashed "+ Adicionar app" tile. Profiles live behind a "Perfis" control in the top bar.

FORM: tile board, the user's locked surface (dealt 2 of 3, position 1 on the page); seed:cb2d8d99ff368095.

Signature move: the route light. When a tile changes route its border and inner glow cross-fade between green and neutral (about 600 ms, ease-out), and the window's top glow follows the overall state, like the searxng mode color.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
