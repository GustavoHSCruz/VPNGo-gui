"""Turn vpngo's cumulative counters into rates, history and readable text."""

import ipaddress
import json
import os
import time
from collections import deque

from .i18n import language, tr


HISTORY = 40        # Samples kept per app: about two minutes at the 3 s refresh.
QUIET = 4 * 1024    # Rates below this still draw a flat line, not a noisy one.
RESUME = 120        # Seconds a saved history stays good: covers a restart, not a day off.


class Traffic:
    """Per-app byte rates from successive snapshots; resets when a counter goes backwards.

    history maps an app to (total rate, route state) samples, oldest first, so the trace
    can show which stretch went through the VPN and which went direct.
    """

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
            if down < 0 or up < 0:  # Closed connections (Mihomo) restart the counters: skip one sample.
                continue
            rates[app.name] = (down / elapsed, up / elapsed)
            history.append((down / elapsed + up / elapsed, app.state))
        return rates

    def save(self, path):
        data = {"saved_at": time.time(),
                "apps": {name: [list(sample) for sample in samples] for name, samples in self.history.items()}}
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(".tmp")
            temporary.write_text(json.dumps(data), encoding="utf-8")
            os.replace(temporary, path)
        except OSError:
            pass

    def load(self, path):
        """Pick up the trace from a recent run (an update or a quick restart)."""
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if time.time() - float(data["saved_at"]) > RESUME:
                return
            for name, samples in data["apps"].items():
                self.history[str(name)] = deque(((float(value), str(state)) for value, state in samples),
                                                maxlen=HISTORY)
        except (OSError, ValueError, KeyError, TypeError):
            self.history.clear()


def bytes_text(value):
    units = ("B", "kB", "MB", "GB", "TB")
    index = 0
    while value >= 1000 and index < len(units) - 1:
        value /= 1000
        index += 1
    text = f"{value:.0f}" if value >= 10 or index == 0 else f"{value:.1f}"
    if language() == "pt-BR":
        text = text.replace(".", ",")
    return f"{text} {units[index]}"


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


def duration_text(seconds):
    seconds = max(0, int(seconds or 0))
    minutes, hours, days = seconds // 60, seconds // 3600, seconds // 86400
    if minutes < 1:
        return tr("uptime_now")
    if hours < 1:
        return f"{minutes} min"
    if days < 1:
        return f"{hours} h {minutes % 60:02d} min"
    return f"{days} d {hours % 24} h"


def short_duration(seconds):
    """The same span in a few characters, for narrow tiles: 0m, 27m, 15h46, 2d3h."""
    seconds = max(0, int(seconds or 0))
    minutes, hours, days = seconds // 60, seconds // 3600, seconds // 86400
    if hours < 1:
        return f"{minutes}m"
    if days < 1:
        return f"{hours}h{minutes % 60:02d}"
    return f"{days}d{hours % 24}h"


def uptime_text(started_at, now=None):
    if not started_at:
        return ""
    return duration_text((time.time() if now is None else now) - started_at)


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
