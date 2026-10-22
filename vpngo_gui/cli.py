"""Run vpngo commands without a terminal and read its machine-readable state.

Commands run in a new session with no controlling terminal, so when vpngo calls
sudo, sudo asks for the password through SUDO_ASKPASS: this app's own dialog
(see askpass.py). On Windows, vpngo raises the UAC prompt itself.
"""

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field

from .i18n import language


STATES = ("vpn", "direct", "partial", "stopped")


@dataclass(frozen=True)
class App:
    name: str
    profile: str
    state: str
    active_profile: str | None = None
    temporary: bool = False
    started_at: float | None = None
    endpoint: str | None = None
    rx_bytes: int | None = None
    tx_bytes: int | None = None

    @property
    def running(self):
        return self.state != "stopped"

    @property
    def shown_profile(self):
        return self.active_profile if self.running and self.active_profile else self.profile


@dataclass(frozen=True)
class Snapshot:
    profiles: tuple = ()
    apps: tuple = ()
    platform: str = field(default=sys.platform)
    version: str = ""

    @property
    def on_vpn(self):
        return sum(1 for app in self.apps if app.state == "vpn")


def number(value, kind=float):
    """Optional numeric field: older vpngo versions omit it."""
    try:
        return kind(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def parse_snapshot(text):
    data = json.loads(text)
    if not isinstance(data, dict) or data.get("schema") != 1:
        raise ValueError("Unsupported vpngo status format; update vpngo.")
    apps = []
    for item in data.get("apps", []):
        state = item.get("state")
        apps.append(App(name=str(item["name"]), profile=str(item.get("profile", "default")),
                        state=state if state in STATES else "partial",
                        active_profile=item.get("active_profile"), temporary=bool(item.get("temporary")),
                        started_at=number(item.get("started_at")), endpoint=item.get("endpoint") or None,
                        rx_bytes=number(item.get("rx_bytes"), int), tx_bytes=number(item.get("tx_bytes"), int)))
    return Snapshot(profiles=tuple(str(name) for name in data.get("profiles", [])), apps=tuple(apps),
                    platform=str(data.get("platform", sys.platform)), version=str(data.get("version", "")))


class CommandError(Exception):
    pass


def command():
    """The vpngo command recorded by `vpngo --install-gui`, else vpngo on PATH."""
    from .engine import prefix
    override = os.environ.get("VPNGO_GUI_CLI")
    recorded = prefix() / "cli.json"
    if override:
        return json.loads(override) if override.startswith("[") else [override]
    if recorded.is_file():
        return json.loads(recorded.read_text(encoding="utf-8"))["command"]
    found = shutil.which("vpngo")
    if not found:
        raise CommandError("vpngo-missing")
    return [found]


def private_engine_in_use():
    """True when the interface runs its own downloaded engine rather than an installed vpngo."""
    from .engine import prefix
    try:
        return str(prefix() / "engine") in " ".join(command())
    except CommandError:
        return False


def run(arguments, environment=None, timeout=120):
    """Run one vpngo command; returns stdout or raises CommandError with vpngo's own message."""
    env = {**os.environ, **(environment or {}), "VPNGO_LANG": language()}
    options = {}
    if os.name == "nt":
        options["creationflags"] = subprocess.CREATE_NO_WINDOW
    else:
        options["start_new_session"] = True  # No terminal: sudo uses SUDO_ASKPASS.
    try:
        result = subprocess.run([*command(), *arguments], stdin=subprocess.DEVNULL, capture_output=True,
                                text=True, env=env, timeout=timeout, check=False, **options)
    except FileNotFoundError:
        raise CommandError("vpngo-missing") from None
    except subprocess.TimeoutExpired:
        raise CommandError(f"vpngo {arguments[0]} did not finish in {timeout} s.") from None
    if result.returncode:
        lines = [line.strip() for line in (result.stderr or result.stdout).splitlines() if line.strip()]
        message = lines[-1] if lines else f"exit code {result.returncode}"
        raise CommandError(message.removeprefix("vpngo: "))
    return result.stdout


def snapshot():
    return parse_snapshot(run(["status", "--json"], timeout=30))
