"""Turn vpngo's cumulative counters into rates, history and readable text."""

import ipaddress
import time
from collections import deque

from .i18n import language, tr


HISTORY = 40        # Samples kept per app: about two minutes at the 3 s refresh.
QUIET = 4 * 1024    # Rates below this still draw a flat line, not a noisy one.


class Traffic:
    """Per-app byte rates from successive snapshots; resets when a counter goes backwards."""

    def __init__(self):
        self.last = {}
        self.history = {}

    def update(self, apps, now=None):
        now = time.monotonic() if now is None else now
        rates = {}
        for app in apps:
            if not app.running or app.rx_bytes is None or app.tx_bytes is None:
                self.last.pop(app.name, None)
                self.history.pop(app.name, None)
                continue
            previous = self.last.get(app.name)
            self.last[app.name] = (now, app.rx_bytes, app.tx_bytes)
            history = self.history.setdefault(app.name, deque(maxlen=HISTORY))
            if previous is None or now <= previous[0]:
                continue
            elapsed = now - previous[0]
            down, up = app.rx_bytes - previous[1], app.tx_bytes - previous[2]
            if down < 0 or up < 0:  # New session or closed connections: start over.
                history.clear()
                continue
            rates[app.name] = (down / elapsed, up / elapsed)
            history.append(down / elapsed + up / elapsed)
        return rates


def rate_text(value):
    units = ("B/s", "kB/s", "MB/s", "GB/s")
    index = 0
    while value >= 1000 and index < len(units) - 1:
        value /= 1000
        index += 1
    text = f"{value:.0f}" if value >= 10 or index == 0 else f"{value:.1f}"
    if language() == "pt-BR":
        text = text.replace(".", ",")
    return f"{text} {units[index]}"


def uptime_text(started_at, now=None):
    if not started_at:
        return ""
    seconds = max(0, int((time.time() if now is None else now) - started_at))
    minutes, hours, days = seconds // 60, seconds // 3600, seconds // 86400
    if minutes < 1:
        return tr("uptime_now")
    if hours < 1:
        return f"{minutes} min"
    if days < 1:
        return f"{hours} h {minutes % 60:02d} min"
    return f"{days} d {hours % 24} h"


def split_endpoint(endpoint):
    """('146.70.230.82', '51820') from '146.70.230.82:51820' or '[2001:db8::1]:51820'."""
    if not endpoint:
        return None, None
    if endpoint.startswith("["):
        host, _, port = endpoint[1:].partition("]:")
        return host, port or None
    host, separator, port = endpoint.rpartition(":")
    return (host, port) if separator and ":" not in host else (endpoint, None)


def masked(host, short=False):
    """Keep the network part readable, hide the rest: 146.70.•••.••• (short: 146.70.•.•) / 2001:db8:•••."""
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        name = host.split(".")
        return "•••." + ".".join(name[-2:]) if len(name) > 2 else "•••"
    if address.version == 4:
        parts = str(address).split(".")
        hidden = "•" if short else "•••"
        return f"{parts[0]}.{parts[1]}.{hidden}.{hidden}"
    groups = address.exploded.split(":")
    return ":".join(group.lstrip("0") or "0" for group in groups[:2]) + ":•••"
