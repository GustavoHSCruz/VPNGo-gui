"""Newer releases of the interface, and of its private engine when it uses one.

Updating goes through vpngo itself: the engine is refreshed first (when the interface
owns one), then `vpngo --install-gui` installs the newest interface beside this one.
A source checkout ("dev") never offers updates.
"""

import json

from . import cli, engine, version


GUI_REPOSITORY = "GustavoHSCruz/VPNGo-gui"


def latest(repository):
    data = json.loads(engine.fetch(f"https://api.github.com/repos/{repository}/releases/latest"))
    tag = str(data.get("tag_name", ""))
    # parse_version needs a word boundary before the number, which "v0.4.0" lacks.
    if not tag.startswith("v") or not engine.parse_version(tag[1:]):
        raise engine.EngineError(f"Could not read the latest release of {repository}.")
    return tag[1:]


def newer(candidate, current):
    candidate, current = engine.parse_version(candidate), engine.parse_version(current)
    return bool(candidate and current and candidate > current)


def outdated_engine():
    """The newer vpngo release when the interface runs its own, older engine; else None."""
    if not cli.private_engine_in_use():
        return None
    _command, text = engine.private_engine()
    available = latest(engine.REPOSITORY)
    return available if newer(available, text or "") else None


def check():
    """The newer interface version, or None. Raises EngineError when offline."""
    current = version()
    if current == "dev":
        return None
    available = latest(GUI_REPOSITORY)
    return available if newer(available, current) else None


def update():
    """Refresh the engine if it is behind, then install the newest interface. Raises on failure."""
    engine_version = outdated_engine()
    if engine_version:
        engine.record(engine.download_engine(engine_version, report=lambda message: None))
    cli.run(["--install-gui"], timeout=900)
