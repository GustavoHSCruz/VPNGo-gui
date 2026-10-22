"""Find vpngo, or download a private copy of it (the interface's engine), then install the interface.

Released as install.py, so the interface can be installed without the vpngo command:

    python3 install.py          (Windows: python install.py)

1. If a compatible `vpngo` is on PATH, the interface uses it.
2. Otherwise (missing, or older than the interface needs) it downloads the vpngo release for
   this system, checks it against SHA256SUMS and keeps it in the interface's folder as its
   engine: the same program, but not added to PATH.
3. That vpngo then runs `--install-gui`, which installs the interface itself.

The interface uses the same functions to download or update its engine from the window.
Standard library only: this file runs before anything else is installed.

VPNGO_VERSION picks the engine release, VPNGO_RELEASE_URL downloads it from another location
(such as a local mirror), and VPNGO_GUI_PREFIX changes the interface folder.
"""

import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path


REPOSITORY = "GustavoHSCruz/VPNGo"
MINIMUM = (0, 5, 0)       # status --json and --install-gui
RECOMMENDED = (0, 6, 0)   # running time, server and traffic on the tiles


class EngineError(Exception):
    pass


def prefix():
    if os.environ.get("VPNGO_GUI_PREFIX"):
        return Path(os.environ["VPNGO_GUI_PREFIX"]).expanduser()
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData/Local") / "vpngo-gui"
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share") / "vpngo-gui"


def system():
    return "windows" if os.name == "nt" else "macos" if sys.platform == "darwin" else "linux"


def parse_version(text):
    """(0, 6, 0) from 'vpngo 0.6.0'; None for 'vpngo dev' (a source checkout) or anything else."""
    match = re.search(r"\b(\d+)\.(\d+)\.(\d+)\b", text or "")
    return tuple(int(part) for part in match.groups()) if match else None


def launcher(root):
    """The command that runs the vpngo installed (or unpacked) at root."""
    if system() == "windows":
        return ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(root / "windows/vpngo.ps1")]
    return [str(root / system() / "vpngo")]


def run_version(command):
    options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
    try:
        result = subprocess.run([*command, "version"], capture_output=True, text=True, timeout=30,
                                stdin=subprocess.DEVNULL, check=False, **options)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def installed_cli():
    """(command, version text) of a vpngo on PATH that the interface can use, else (None, reason)."""
    found = shutil.which("vpngo")
    if not found:
        return None, "missing"
    text = run_version([found])
    if text is None:
        return None, "broken"
    version = parse_version(text)
    if text.strip() != "vpngo dev" and (version is None or version < MINIMUM):
        return None, f"old:{text}"
    return [found], text


def private_engine():
    """The engine this interface downloaded earlier, if any."""
    root = prefix() / "engine/app"
    if not root.is_dir():
        return None, None
    text = run_version(launcher(root))
    return (launcher(root), text) if text else (None, None)


def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": "vpngo-gui"})
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return response.read()
    except OSError as error:
        raise EngineError(f"Could not download {url}: {error}") from None


def latest_version():
    data = json.loads(fetch(f"https://api.github.com/repos/{REPOSITORY}/releases/latest"))
    tag = str(data.get("tag_name", ""))
    if not tag.startswith("v"):
        raise EngineError("Could not find the latest vpngo release.")
    return tag[1:]


def download_engine(version=None, report=print):
    """Download, verify and unpack the vpngo release as this interface's engine; returns its command."""
    version = version or os.environ.get("VPNGO_VERSION") or latest_version()
    name = f"vpngo-{version}-{system()}"
    asset = name + (".zip" if system() == "windows" else ".tar.gz")
    base = os.environ.get("VPNGO_RELEASE_URL") or f"https://github.com/{REPOSITORY}/releases/download/v{version}"
    report(f"Downloading the vpngo {version} engine...")
    archive = fetch(f"{base}/{asset}")
    sums = fetch(f"{base}/SHA256SUMS").decode("utf-8")
    expected = next((line.split()[0] for line in sums.splitlines()
                     if len(line.split()) == 2 and line.split()[1].lstrip("*") == asset), None)
    if not expected:
        raise EngineError(f"{asset} is not listed in SHA256SUMS.")
    if hashlib.sha256(archive).hexdigest() != expected:
        raise EngineError(f"Checksum mismatch for {asset}; the download is corrupt or was altered.")
    report("Checksum verified.")
    engine = prefix() / "engine"
    engine.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=engine) as temporary:
        work = Path(temporary)
        if asset.endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(archive)) as source:
                source.extractall(work)
        else:
            with tarfile.open(fileobj=io.BytesIO(archive)) as source:
                source.extractall(work, filter="data")
        unpacked = work / name
        if not (unpacked / "shared/commands.py").is_file():
            raise EngineError("The vpngo archive has an unexpected layout.")
        if run_version(launcher(unpacked)) != f"vpngo {version}":
            raise EngineError("The downloaded vpngo engine did not start; check that Python 3 is installed.")
        old = engine / "app.old"
        shutil.rmtree(old, ignore_errors=True)
        if (engine / "app").exists():
            (engine / "app").rename(old)
        unpacked.rename(engine / "app")
        shutil.rmtree(old, ignore_errors=True)
    report(f"vpngo {version} engine ready in {engine / 'app'} (not added to PATH).")
    return launcher(engine / "app")


def choose_engine(report=print):
    """The vpngo command the interface should use, downloading the engine when needed."""
    command, detail = installed_cli()
    if command:
        report(f"Using the installed {detail} ({command[0]}).")
        version = parse_version(detail)
        if version and version < RECOMMENDED:
            report("Tip: update vpngo to see running time, traffic and the VPN server on each app.")
        return command
    if detail.startswith("old:"):
        report(f"The installed {detail[4:]} is too old for the interface; it gets its own engine instead. "
               "Updating vpngo lets both share one copy.")
    elif detail == "broken":
        report("The vpngo on PATH did not run; the interface gets its own engine instead.")
    command, text = private_engine()
    current = parse_version(text)
    if command and current and current >= MINIMUM and not os.environ.get("VPNGO_VERSION"):
        try:
            latest = parse_version(latest_version())
        except EngineError:
            latest = None  # Offline: the engine already here is good enough.
        if latest is None or latest <= current:
            report(f"Using the interface's {text} engine.")
            return command
    return download_engine(report=report)


def record(command):
    """Tell the interface which vpngo to run (vpngo --install-gui writes the same file)."""
    path = prefix() / "cli.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"command": command}, indent=2) + "\n", encoding="utf-8")


def main():
    try:
        command = choose_engine()
        print("Installing the VPNGo interface...", flush=True)
        options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
        return subprocess.run([*command, "--install-gui"], check=False, **options).returncode
    except EngineError as error:
        print(f"vpngo-gui installer: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
