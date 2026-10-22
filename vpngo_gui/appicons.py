"""Each app's own icon: from its desktop entry on Linux, from the program itself elsewhere."""

import os
import re
import shlex
import sys
from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QFileInfo
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QFileIconProvider


def data_dirs():
    home = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share")
    system = [Path(path) for path in (os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share").split(":")
              if path]
    flatpak = [home / "flatpak/exports/share", Path("/var/lib/flatpak/exports/share")]
    return [home, *flatpak, *system]


@lru_cache(maxsize=1)
def desktop_index():
    """{lowercase key: Icon value} from every desktop entry.

    Keys by strength: the entry's file name first, then the program it runs, then its Name,
    so a game's launcher (which also runs `steam`) never takes Steam's own icon.
    """
    by_file, by_program, by_name = {}, {}, {}
    for directory in data_dirs():
        applications = directory / "applications"
        if not applications.is_dir():
            continue
        for entry in sorted(applications.rglob("*.desktop")):
            try:
                text = entry.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            section = text.split("[Desktop Entry]", 1)[-1].split("\n[", 1)[0]
            fields = dict(re.findall(r"^(Icon|Exec|Name)=(.*)$", section, re.M))
            icon = fields.get("Icon", "").strip()
            if not icon:
                continue
            by_file.setdefault(entry.stem.casefold(), icon)
            by_file.setdefault(entry.stem.rsplit(".", 1)[-1].casefold(), icon)  # com.vendor.App
            try:
                program = shlex.split(fields.get("Exec", ""))
            except ValueError:
                program = []
            words = [word for word in program if not word.startswith("%") and "=" not in word]
            if words:
                first = Path(words[0]).name
                # `env FOO=bar program` names the real program next.
                by_program.setdefault((Path(words[1]).name if first == "env" and len(words) > 1 else first).casefold(),
                                      icon)
            if fields.get("Name"):
                by_name.setdefault(fields["Name"].strip().casefold(), icon)
    return {**by_name, **by_program, **by_file}


@lru_cache(maxsize=256)
def themed_file(name):
    """An icon name resolved in hicolor or pixmaps; Qt's own theme lookup is empty outside a desktop session."""
    for directory in data_dirs():
        for pattern in (f"icons/hicolor/scalable/apps/{name}.svg", f"icons/hicolor/512x512/apps/{name}.png",
                        f"icons/hicolor/256x256/apps/{name}.png", f"icons/hicolor/128x128/apps/{name}.png",
                        f"icons/hicolor/64x64/apps/{name}.png", f"icons/hicolor/48x48/apps/{name}.png",
                        f"pixmaps/{name}.svg", f"pixmaps/{name}.png"):
            path = directory / pattern
            if path.is_file():
                return str(path)
    return None


@lru_cache(maxsize=256)
def app_icon(name, executable=None):
    """The app's icon, or None when it has none we can find."""
    if sys.platform.startswith("linux"):
        index = desktop_index()
        candidates = [name]
        if executable:
            candidates += [Path(executable).name, Path(executable).resolve().name]
        for candidate in candidates:
            value = index.get(candidate.casefold())
            if not value:
                continue
            if os.path.isabs(value):
                return QIcon(value) if Path(value).is_file() else None
            themed = QIcon.fromTheme(value)
            if not themed.isNull():
                return themed
            path = themed_file(value)
            if path:
                return QIcon(path)
        return None
    if executable and Path(executable).exists():
        result = QFileIconProvider().icon(QFileInfo(executable))
        return None if result.isNull() else result
    return None
