---
name: VPNGo
description: A tray-resident board of app tiles, each lit by its network route.
colors:
  ground: "#111113"
  surface: "#19191c"
  hairline: "#26262a"
  text: "#e9e7e2"
  muted: "#8b8984"
  route-green: "#4cc38a"
  route-green-border: "#376d55"
  route-green-focus: "#429c72"
  partial-amber: "#e0a458"
  danger-coral: "#e5736b"
  stopped-surface: "#141417"
  stopped-text: "#93918f"
  disabled-ink: "#545351"
  white: "#ffffff"
typography:
  title:
    fontFamily: "Inter"
    fontSize: "20px"
    fontWeight: 600
    letterSpacing: "-0.2px"
  headline:
    fontFamily: "Inter"
    fontSize: "18px"
    fontWeight: 600
  wordmark:
    fontFamily: "Inter"
    fontSize: "15px"
    fontWeight: 600
    letterSpacing: "-0.15px"
  body:
    fontFamily: "Inter"
    fontSize: "14px"
    fontWeight: 400
    fontFeature: "\"cv11\" 1, \"ss03\" 1"
  label:
    fontFamily: "Inter"
    fontSize: "13px"
    fontWeight: 400
    fontFeature: "\"cv11\" 1, \"ss03\" 1"
  caption:
    fontFamily: "Inter"
    fontSize: "12px"
    fontWeight: 400
  data:
    fontFamily: "JetBrains Mono"
    fontSize: "13px"
    fontWeight: 400
  data-small:
    fontFamily: "JetBrains Mono"
    fontSize: "12px"
    fontWeight: 400
rounded:
  check: "5px"
  item: "8px"
  control: "10px"
  float: "12px"
  tile: "14px"
  pill: "17px"
spacing:
  hairline-gap: "6px"
  inline: "8px"
  field: "10px"
  column-gap: "14px"
  tile-inset: "18px"
  edge: "20px"
  row-gap: "22px"
  dialog: "24px"
components:
  button-primary:
    backgroundColor: "{colors.text}"
    textColor: "{colors.ground}"
    rounded: "{rounded.pill}"
    padding: "0 16px"
    height: "34px"
  button-primary-hover:
    backgroundColor: "{colors.white}"
    textColor: "{colors.ground}"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.muted}"
    rounded: "{rounded.pill}"
    padding: "0 16px"
    height: "34px"
  button-ghost-hover:
    textColor: "{colors.text}"
  button-tile-start:
    backgroundColor: "transparent"
    textColor: "{colors.muted}"
    rounded: "14px"
    padding: "0 14px"
    height: "28px"
  icon-button:
    backgroundColor: "transparent"
    rounded: "{rounded.control}"
    size: "32px"
  icon-button-hover:
    backgroundColor: "{colors.hairline}"
  summary-pill:
    backgroundColor: "transparent"
    textColor: "{colors.muted}"
    typography: "{typography.label}"
    rounded: "{rounded.pill}"
    padding: "0 14px 0 12px"
    height: "34px"
  input:
    backgroundColor: "{colors.ground}"
    textColor: "{colors.text}"
    rounded: "{rounded.control}"
    padding: "0 12px"
    height: "36px"
  app-tile:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.tile}"
    padding: "14px 14px 16px 18px"
    height: "196px"
  app-tile-stopped:
    backgroundColor: "{colors.stopped-surface}"
    textColor: "{colors.stopped-text}"
  add-tile:
    backgroundColor: "transparent"
    textColor: "{colors.muted}"
    typography: "{typography.body}"
    rounded: "{rounded.tile}"
    height: "196px"
  tile-uptime:
    textColor: "{colors.muted}"
    typography: "{typography.data-small}"
  tile-rates:
    textColor: "{colors.muted}"
    typography: "{typography.data-small}"
    height: "28px"
  tile-total-rate:
    textColor: "{colors.muted}"
    typography: "{typography.data-small}"
    height: "18px"
  server-line:
    textColor: "{colors.muted}"
    typography: "{typography.data-small}"
    height: "18px"
  server-line-hover:
    textColor: "{colors.text}"
  server-line-focus:
    textColor: "{colors.route-green-focus}"
  route-switch:
    backgroundColor: "{colors.hairline}"
    rounded: "10px"
    width: "34px"
    height: "20px"
  route-switch-on:
    backgroundColor: "{colors.route-green-border}"
    textColor: "{colors.text}"
  message-bar:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.float}"
    padding: "10px 8px 10px 16px"
  menu:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.float}"
    padding: "6px"
  menu-item:
    typography: "{typography.label}"
    rounded: "{rounded.item}"
    padding: "8px 28px 8px 12px"
  menu-item-selected:
    backgroundColor: "{colors.hairline}"
---

# Design System: VPNGo

## Overview

**Creative North Star: "The Route Is the Light"**

VPNGo is a small dark board the user opens from the tray, reads in one glance, and closes. Every managed app is a tile, and the tile's light is its route: lit green while the app is on the VPN, unlit warm grey on the direct route, amber when the route cannot be confirmed, and sunk into the ground, hollow-dotted and dimmed, when the app is stopped. Color is read before any word; text confirms what the light already said.

The world is inherited, binding, from the owner's local search site: warm near-black neutrals, Inter for language, JetBrains Mono only for data, one connection color that carries state, 14px cards with an inset top highlight and a long soft shadow, and a faint radial glow at the top of the window that takes the overall state's color. Density is low and calm: three columns of 196px tiles at the default 760x520, generous inner space above the app name, nothing that looks like a settings table.

Motion is state, never decoration. Route changes cross-fade the tile border, top tint and state dot over 600ms ease-out; the window glow follows the same curve; a busy app's dot breathes its halo on an 1100ms sine loop. Refresh never moves or rebuilds a tile under the pointer or a focused control, and live figures never shift the layout: every rate sits in a fixed-width slot.

**Key Characteristics:**
- Warm near-black ground with a single semantic accent (route green), plus amber for unverifiable routes and coral for failures.
- Tiles are the only shadowed objects; everything else is flat with 1px hairlines.
- Inter for words, JetBrains Mono for data and measurements: profile names, paths, addresses, uptime and rates.
- Pills and rounded rectangles only; no sharp corners anywhere.
- State is painted (dots, switch fill, border tint), and every state change animates.

## Colors

A warm charcoal palette where green is a signal, not a brand flourish.

### Primary
- **Route Green** (route-green): the connection color. Fills the state dot and its halo for an app on the VPN, the checked checkbox, the success message dot, and the overall-state top glow. At 45% over the hairline (route-green-border) it becomes the lit tile border, the switch's on-track and the focused input border; at 75% (route-green-focus) it is the focus ring on buttons and switches; at 8% it tints the top of a lit tile.

### Secondary
- **Partial Amber** (partial-amber): a route that is on but cannot be verified. Tints the tile border and top like green at half strength, colors the dot, and colors the tile's detail line ("verificar").

### Tertiary
- **Danger Coral** (danger-coral): failures only. Error message bar dot, a 35% border and a 6% fill on the floating bar, and dialog validation text.

### Neutral
- **Ground** (ground): window background, input wells, the ink of the primary button.
- **Surface** (surface): tiles, dialogs, menus, tooltips, the message bar.
- **Hairline** (hairline): every 1px border, menu separators, the switch's off-track, hover fill on icon buttons and menu items.
- **Bone Text** (text): primary text, the primary button's fill, the switch knob when on.
- **Warm Muted** (muted): secondary text, idle icons, ghost button labels, the direct-route dot, the switch knob when off.
- **Sunk Surface** (stopped-surface) and **Stopped Text** (stopped-text): a stopped tile's surface (surface 60% toward ground) and dimmed app name.
- **Disabled Ink** (disabled-ink): disabled button text and icons.

### Named Rules
**The Green Means On Rule.** Route green appears only where something is on, affirmative or focused: VPN route, checked box, success, keyboard focus, the overall glow. It never decorates a heading, a logo treatment or an idle control.

**The Mixed, Not Invented Rule.** Intermediate tones are mixes of the palette (hairline toward green, surface toward ground, muted toward ground), not new hexes. New states derive the same way.

## Typography

**Display Font:** none; the largest type is the 20px tile title.
**Body Font:** Inter (bundled variable font, cv11 and ss03 on, hinting off)
**Label/Mono Font:** JetBrains Mono (bundled variable font)

**Character:** A quiet humanist-grotesque UI voice with a mono counter-voice reserved for machine data, so a profile name like "br" reads as an identifier, not a word.

### Hierarchy
- **Title** (600, 20px, -0.2px): the app name on each tile and the empty-state heading.
- **Headline** (600, 18px): dialog headings.
- **Wordmark** (600, 15px, -0.15px): "VPNGo" in the top bar; plain type, no logo lockup in the window.
- **Body** (400, 14px): application default; the add-tile label, checkbox text, empty-state body.
- **Label** (400, 13px): buttons, menu items, the summary pill (+0.2px), the tile detail line, dialog errors.
- **Caption** (400, 12px): field captions above inputs, in muted.
- **Data** (JetBrains Mono 400, 13px): profile names, file paths in inputs, the profile combo.
- **Data Small** (JetBrains Mono 400, 12px): the profile inside the tile detail line and every tile measurement: uptime, the ↓/↑ rates, the compact total and the server address.

### Named Rules
**The Data Is Mono Rule.** Data and measurements set in JetBrains Mono: profile names, file paths, server addresses, uptime and transfer rates (units included, "58 kB/s", "4 h 59 min"). Route words, actions and labels set in Inter, even on the same line ("us · VPN"). One accepted exception, the owner's call: profile names inside QMenus (tile and tray menus) stay in Inter so they remain plain checkable items, one click deep and arrow-key navigable.

## Layout

A responsive tile board inside a fixed top bar. The window opens 760px wide (minimum 300x360) with a 20px edge on all sides, as tall as its tiles need (up to 85% of the screen) and only after vpngo's first answer, so it never opens mostly empty and then grows. A tiling window manager may size it anyway. Once the user resizes it, the saved size wins. The top bar (16px top, 12px bottom, 14px right) holds the wordmark left, then the summary pill, the "Perfis" pill and the settings icon button right, 8px apart.

The board lays tiles in as many columns as fit, 1 to 4, each at least 210px wide and exactly 196px tall, with a 14px column gap and a 22px row gap (the row gap leaves room for each tile's shadow). The dashed add tile always occupies the last cell. Groups put a 46px heading row across every column before their tiles; when groups exist, the remaining apps follow under an "Outros apps" heading. Tiles are moved, never rebuilt, when the column count changes. The floating message bar sits 20px from the sides and 16px from the bottom; the board gains bottom inset instead of reflowing.

Tile interior: 18px left, 14px top/right, 16px bottom. Top row: state dot, 6px, uptime (taking the free width), overflow button. A flexible gap (where the traffic trace lives), then the heading row (title, 10px, rates on wide cards), 2px, the 18px server line (address left, compact total right), 6px, and a 28px detail row (detail text, 10px, switch or start button).

**The Compact Card Rule.** A card narrower than 260px is compact: the stacked ↓/↑ rates beside the name collapse into one combined total at the right of the server line, and the masked address shortens to one bullet per hidden part (146.70.•.•). A revealed address needs that room, so the total steps aside while the address is shown. The switch is the card's width, measured on every resize, not the window's. Dialogs: 420px minimum width, 24/22/24/20 padding, field caption 6px above its control, 10px between fields, actions right-aligned with 8px between.

## Elevation & Depth

Hybrid: tonal layering for everything, one real shadow for tiles. Surfaces step from ground to surface; borders are 1px hairlines. Tiles additionally carry a white inset highlight line along the top edge (9/255 alpha, inset 14px from the corners) and a long soft shadow falling below them. A stopped tile loses both its shadow and its highlight and its surface sinks toward the ground, so a stopped app reads as switched off before its dot is seen. The window's top radial glow (5% alpha muted when nothing is on the VPN, up to 12% alpha green when something is) is atmosphere, not elevation.

### Shadow Vocabulary
- **Tile fall** (painted equivalent of `box-shadow: 0 12px 32px -16px rgb(0 0 0 / .6)`): 16 stacked translucent black layers, each narrowing 0.35px per side and dropping about 1px further, reaching about 18px below the card. Running tiles only; scales with the alive level.
- **Tile highlight** (`inset 0 1px 0 rgb(255 255 255 / .035)`): the top-edge line on running tiles.

### Named Rules
**The Only Tiles Float Rule.** Shadows belong to app tiles. Pills, buttons, inputs, menus, dialogs and the message bar stay flat and are separated by hairlines and tone.

## Shapes

Everything is rounded, on a small set of radii: 5px checkbox squares, 8px menu items and tooltips, 10px inputs, combos and icon buttons, 12px menus and the message bar, 14px tiles (and the app icon), and full pills (17px on 34px controls, 14px on the 28px start button, 10px on the switch track). Borders are always 1px. The add tile alone uses a dashed hairline, marking an empty slot rather than an object. Round state dots (7px core, 13px halo) are the only circles besides the switch knob.

## Components

### Buttons
Quiet pills that brighten on intent.
- **Shape:** full pill (34px tall, 17px radius).
- **Primary:** bone fill with ground ink, 600 weight; hover goes to pure white. One per view: the confirm action in a dialog, the empty-state action.
- **Ghost (default):** transparent, hairline border, muted label; hover brightens the label to text and tints the border halfway to green; pressed fills with hairline; focus tints the border 75% toward green.
- **Tile start:** a 28px ghost pill ("Iniciar") that replaces the route switch on a stopped tile.
- **Icon button:** 32px, 10px radius, 18px SVG icon in muted (text on hover), hairline fill on hover or focus. Used for the tile overflow and message dismiss.
- **Pill with icon ("Perfis"):** painted ghost pill whose icon and label ink is optically centred.

### Chips
- **Summary pill:** hairline pill holding a state dot and "2 de 4 na VPN" in 13px muted; the dot is green when any app is on the VPN.

### Cards / Containers
- **Corner Style:** 14px.
- **Background:** surface, vertically graded from a route-tinted top (8% of green or amber, plus 2% on hover) to plain surface.
- **Shadow Strategy:** the tile fall and highlight (see Elevation & Depth).
- **Border:** hairline, mixed up to 45% toward the route color as the light rises; hover adds 25% more toward muted or the accent.
- **Internal Padding:** 14px top/right, 16px bottom, 18px left.

### Inputs / Fields
- **Style:** 36px, ground well, hairline border, 10px radius, 12px horizontal padding; paths and profile names in mono.
- **Focus:** border goes 45% toward green; selection uses the same mix.
- **Error / Disabled:** errors are a coral line of text above the dialog actions; disabled text drops to muted.

### Navigation
- **Menus:** surface, hairline border, 12px radius, 6px padding; 13px items with 8px radius, hairline fill when selected, hairline separators; the current profile is marked with a small green dot. Profiles sit inline under a disabled header so switching is one click from the open menu.

### Route Switch (signature)
The searxng switch: a 34x20 track (10px radius) that fills from hairline to green-over-hairline as a 14px knob slides right in 200ms ease-out and turns from muted to text. Hover lifts the knob 25% toward white; focus draws a 2px ring at 75% green around the track.

### State Dot (signature)
A 7px light with a 13px halo at 22% alpha in the state color. Stopped is a hollow 1px ring; busy breathes the halo (22% to 47% alpha, 6.5px to 8px radius). Color changes cross-fade over 600ms.

### Route Time
How long the app has been on its current route (since it was last switched, not since it opened), quiet in the top row: Data Small in muted ("23 min", "4 h 59 min", "2 d 3 h"). When the whole line fits, the other route's total follows after a spaced middle dot ("10 min  ·  VPN 15 h 36 min"); when it does not, only the current figure shows, never a cut one. The tooltip lists the time on this route, the total on each route, the data moved on this route and how long the app has been open. Running apps only; a stopped tile's top row holds just the hollow dot.

### Rates
Download over upload, stacked in two 14px lines right of the app name on cards 260px and wider, bottom-aligned with the title. Data Small in muted, right-aligned, each followed by a drawn 10px arrow icon (↓ then ↑, never a glyph). The slot is fixed at the width of "000 kB/s" plus the arrow, so the title's cut point never moves between refreshes; empty until a first rate is known.

### Compact Total
On compact cards (under 260px) the rates become one figure: the ↓↑ drawn icon pair, then download plus upload as one rate, Data Small in muted, in an 18px slot of the same fixed width at the right of the server line. Its tooltip carries the separate figures. It hides while the address is revealed.

### Address Line
The address under the app name, Data Small, masked by default to keep the network part readable (146.70.•••.•••; 146.70.•.• on compact cards; IPv6 keeps two groups then •••). Click, Enter or Space toggles the full address. On the VPN (or partial) it is the VPN server's address, and the tooltip gives the port. On the direct route it is the public IP: it starts fully masked (•••.•••.•••.•••, the same shape, so nothing moves when it arrives) and is looked up from an outside IPv4 service only when clicked, kept five minutes and shared by every direct tile. Muted at rest, text on hover and while looking up, route-green-focus when keyboard-focused. Stopped tiles leave the line empty.

### App Icon
The app's own icon, 24px, left of the title with a 10px gap: its desktop entry's icon on Linux (matched by entry file name first, then the program it runs, then its name), the executable's icon on macOS and Windows. Absent when none is found; the title then starts at the edge as before.

### Traffic Trace (signature)
The last two minutes of traffic (40 samples, one per 3s refresh) as a faint area behind the tile's empty middle, in the band from 44px below the card top to mid-card, so it never runs under text. Area filled top to bottom from 10% to 0 alpha, topped by a 1.2px line at 32% alpha whose oldest 40px fade in from nothing. Each stretch is coloured by the route its samples took: green on the VPN, muted grey on the direct route, amber where the route was partial; a stretch starts at the previous one's last point, so the line never breaks. Drawn only once 20 samples exist, only on running tiles, and never when every sample is under 4 KiB/s: a flat idle line would read as a divider. Scaled to the peak, never below 16 KiB/s; clipped to the 14px card shape. The samples survive a restart of under two minutes (an update), not a day off.

### Group Heading
A 46px row across the board above a group's tiles, aligned with the cards' left edge: the group name in 14px Inter 600, the count "1 de 2 na VPN" in Data Small muted (the busy word while the group acts), then right-aligned a route switch (on when every app in the group is on the VPN) and an overflow menu (turn all on, turn all off, stop all, the profile list, delete the group). The "Outros apps" heading is the name alone, in muted.

### Message Bar
A floating 12px-radius bar over the board's bottom: state dot, wrapping selectable text, an optional 28px ghost pill for the one thing to do next ("Atualizar", "Reabrir"), and the dismiss button. Success is tinted green and leaves after 6s; errors are tinted coral, and a bar with an action stays until answered or dismissed.

### Settings
A 32px icon button (sliders) at the right of the top bar opens a menu: language (Automatic, Português (Brasil), English; choosing one rebuilds the window in place), start with the system, notify when an app leaves the VPN without being asked, the version, and either "Procurar atualizações" or "Atualizar para x.y.z".

### Add Tile
A dashed hairline slot the size of a tile, centred plus icon and "Adicionar app" in 14px muted; hover brightens the border toward muted with a 2% white fill, focus tints it toward green.

## Do's and Don'ts

### Do:
- **Do** let the tile itself carry the route: border, top tint and dot change together over 600ms ease-out.
- **Do** derive new tones by mixing palette colors (the Mixed, Not Invented Rule) instead of adding hexes.
- **Do** set profile names, paths, addresses, uptime and rates in JetBrains Mono and every word around them in Inter.
- **Do** give every live figure a fixed-width slot ("000 kB/s") so refreshes never move the text beside it.
- **Do** keep a stopped app visibly sunk: no shadow, no highlight, dimmed title, hollow dot, "Iniciar" in place of the switch.
- **Do** keep at most one bone primary button per view; everything else is a ghost pill.
- **Do** update state in place; never move or rebuild a tile, menu or control the user is pointing at or focused on.

### Don't:
- **Don't** arrange apps as rows of names with a status column; apps are tiles on a board.
- **Don't** use route green for anything that is not on, affirmative or focused.
- **Don't** add shadows to anything but app tiles.
- **Don't** introduce sharp corners or borders heavier than 1px.
- **Don't** use mono for labels, actions or route words.
