"""What VPNGo Setup does on Windows, without the window: install, upgrade and uninstall.

It installs the latest vpngo release the way install-windows.ps1 does (the archive, checked
against SHA256SUMS, swapped into %LOCALAPPDATA%\\vpngo\\app, then windows\\install.ps1 for the
command), then the interface through `vpngo --install-gui`, a Start menu shortcut and an entry
in Settings > Apps. Settings, profiles and the interface's history are never touched.

Standard library only, so the silent mode needs nothing else. Each step reports through
callbacks; the window and the silent mode share this code.
"""

import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path

REPOSITORY = "GustavoHSCruz/VPNGo"
UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\VPNGo"
INNO_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\{6B1E5C7A-3F2D-4B8E-9A61-2C0D7E4F9B13}_is1"
MSI_KEY = r"Software\vpngo\msi"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# Exit codes, the same as the Inno setup's: 1 failed before vpngo was installed.
COMMAND_FAILED, PROXIFYRE_FAILED, GUI_FAILED, PYTHON_MISSING = 10, 11, 12, 13


class SetupError(Exception):
    def __init__(self, message, code=1):
        super().__init__(message)
        self.code = code


def local():
    return Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData/Local")


def prefix():
    return Path(os.environ.get("VPNGO_PREFIX") or local() / "vpngo")


def gui_root():
    return local() / "vpngo-gui"


def shortcut():
    return Path(os.environ.get("APPDATA") or Path.home() / "AppData/Roaming") / \
        "Microsoft/Windows/Start Menu/Programs/VPNGo.lnk"


def powershell():
    return str(Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32/WindowsPowerShell/v1.0/powershell.exe")


# --- Registry ----------------------------------------------------------------------------

def registry_value(key, name):
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as handle:
            return winreg.QueryValueEx(handle, name)[0]
    except OSError:
        return None


def user_path():
    """The user PATH as stored, so a Python installed during this run is found."""
    machine = os.environ.get("PATH", "")
    stored = registry_value("Environment", "Path") or ""
    return ";".join(part for part in (stored + ";" + machine).split(";") if part)


# --- Running things ----------------------------------------------------------------------

def run(command, log, env=None, timeout=1800):
    """Run a command without a console window, sending each output line to log."""
    environment = dict(os.environ, PATH=user_path(), **(env or {}))
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                               env=environment, creationflags=NO_WINDOW, text=True, encoding="utf-8", errors="replace")
    started = time.monotonic()
    for line in process.stdout:
        if line.strip():
            log(line.rstrip())
        if time.monotonic() - started > timeout:
            process.kill()
            raise SetupError(f"{command[0]} took too long.")
    return process.wait()


def script(path, log, *arguments):
    return run([powershell(), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(path), *arguments], log)


# --- Python ------------------------------------------------------------------------------

def python():
    """The Python vpngo will run (VPNGO_PYTHON or python on PATH), if it really is Python 3."""
    candidate = os.environ.get("VPNGO_PYTHON") or shutil.which("python", path=user_path())
    # The Microsoft Store's python.exe alias only opens the Store.
    if not candidate or "WindowsApps" in candidate:
        return None
    try:
        result = subprocess.run([candidate, "-c", "import sys; print(sys.version_info[0])"], capture_output=True,
                                text=True, timeout=30, creationflags=NO_WINDOW)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return candidate if result.returncode == 0 and result.stdout.strip() == "3" else None


def install_python(log):
    """Install Python for this user with winget, as the Windows guide does by hand."""
    winget = shutil.which("winget")
    if not winget:
        raise SetupError("Python 3 is missing and winget is not available to install it.", PYTHON_MISSING)
    code = run([winget, "install", "--id", "Python.Python.3.13", "-e", "--scope", "user", "--silent",
                "--accept-package-agreements", "--accept-source-agreements", "--disable-interactivity"], log)
    if not python():
        raise SetupError(f"Python could not be installed (winget exit {code}).", PYTHON_MISSING)


# --- Downloading -------------------------------------------------------------------------

def fetch(url, progress=None):
    request = urllib.request.Request(url, headers={"User-Agent": "vpngo-setup"})
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            total = int(response.headers.get("Content-Length") or 0)
            buffer = io.BytesIO()
            while chunk := response.read(64 * 1024):
                buffer.write(chunk)
                if progress and total:
                    progress(buffer.tell(), total)
            return buffer.getvalue()
    except OSError as error:
        raise SetupError(f"Could not download {url}: {error}") from None


def latest_version():
    if os.environ.get("VPNGO_VERSION"):
        return os.environ["VPNGO_VERSION"]
    tag = str(json.loads(fetch(f"https://api.github.com/repos/{REPOSITORY}/releases/latest")).get("tag_name", ""))
    if not tag.startswith("v"):
        raise SetupError("Could not find the latest vpngo release.")
    return tag[1:]


def expected_hash(sums, asset):
    for line in sums.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1].lstrip("*") == asset:
            return parts[0].lower()
    raise SetupError(f"{asset} is not listed in SHA256SUMS.")


def download(version, progress):
    """The verified vpngo-<version>-windows.zip."""
    asset = f"vpngo-{version}-windows.zip"
    base = os.environ.get("VPNGO_RELEASE_URL") or f"https://github.com/{REPOSITORY}/releases/download/v{version}"
    sums = fetch(f"{base}/SHA256SUMS").decode("utf-8")
    archive = fetch(f"{base}/{asset}", progress)
    if hashlib.sha256(archive).hexdigest() != expected_hash(sums, asset):
        raise SetupError(f"Checksum mismatch for {asset}; the download is corrupt or was altered.")
    return archive


# --- Steps -------------------------------------------------------------------------------

def check_other_installers(log):
    """The MSI is managed by its owner; the older setup is replaced (settings are kept)."""
    if registry_value(MSI_KEY, "path"):
        raise SetupError("vpngo is installed by its MSI package. Uninstall it in Settings > Apps first.")
    uninstaller = registry_value(INNO_KEY, "UninstallString")
    if uninstaller:
        log("Replacing the previous vpngo setup (settings and profiles are kept)...")
        run([uninstaller.strip('"'), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"], log)
        for _ in range(30):  # Its uninstaller finishes in a helper process.
            if not registry_value(INNO_KEY, "UninstallString"):
                break
            time.sleep(1)


def install_files(archive, version, log):
    """Swap the new release into <prefix>\\app, keeping the old one until the new one works."""
    root = prefix()
    root.mkdir(parents=True, exist_ok=True)
    app, new, old = root / "app", root / "app.new", root / "app.old"
    shutil.rmtree(new, ignore_errors=True)
    shutil.rmtree(old, ignore_errors=True)
    with tempfile.TemporaryDirectory(dir=root) as temporary:
        with zipfile.ZipFile(io.BytesIO(archive)) as source:
            source.extractall(temporary)
        unpacked = Path(temporary) / f"vpngo-{version}-windows"
        if not (unpacked / "shared/commands.py").is_file():
            raise SetupError("The vpngo archive has an unexpected layout.")
        unpacked.rename(new)
    if app.exists():
        app.rename(old)
    new.rename(app)
    log(f"vpngo {version} unpacked in {app}.")


def restore_previous():
    root = prefix()
    if (root / "app.old").exists():
        shutil.rmtree(root / "app", ignore_errors=True)
        (root / "app.old").rename(root / "app")


def install_command(version, interpreter, log):
    app = prefix() / "app"
    if script(app / "windows/install.ps1", log):
        raise SetupError("The vpngo command could not be created.", COMMAND_FAILED)
    result = subprocess.run([interpreter, str(app / "shared/commands.py"), "version"], capture_output=True, text=True,
                            creationflags=NO_WINDOW)
    if result.stdout.strip() != f"vpngo {version}":
        raise SetupError("The installed vpngo did not start: " + (result.stderr.strip() or result.stdout.strip()),
                         COMMAND_FAILED)
    shutil.rmtree(prefix() / "app.old", ignore_errors=True)


def stop_gui(log):
    stopper = prefix() / "app/windows/stop-gui.ps1"
    if stopper.is_file():
        script(stopper, log)


def install_gui(log):
    stop_gui(log)
    app = prefix() / "app"
    if script(app / "windows/vpngo.ps1", log, "--install-gui"):
        raise SetupError("The graphical interface could not be installed.", GUI_FAILED)
    make_shortcut(log)


def make_shortcut(log):
    root = gui_root()
    icon = prefix() / "setup/vpngo.ico"
    target = root / "venv/Scripts/pythonw.exe"
    link = shortcut()
    link.parent.mkdir(parents=True, exist_ok=True)
    quote = lambda value: "'" + str(value).replace("'", "''") + "'"
    command = (f"$s = (New-Object -ComObject WScript.Shell).CreateShortcut({quote(link)}); "
               f"$s.TargetPath = {quote(target)}; $s.Arguments = {quote(chr(34) + str(root / 'app/run.py') + chr(34))}; "
               f"$s.WorkingDirectory = {quote(root / 'app')}; $s.Description = 'Route apps through WireGuard'; "
               + (f"$s.IconLocation = {quote(str(icon) + ',0')}; " if icon.is_file() else "") + "$s.Save()")
    if run([powershell(), "-NoProfile", "-Command", command], log):
        raise SetupError("The Start menu shortcut could not be created.", GUI_FAILED)


def install_proxifyre(log):
    if script(prefix() / "app/windows/install-backend.ps1", log):
        raise SetupError("ProxiFyre setup failed or needs a restart. vpngo is installed; run "
                         "windows\\install-backend.ps1 later.", PROXIFYRE_FAILED)


def register(version, setup_exe, gui):
    """Copy this setup beside vpngo and list VPNGo in Settings > Apps, uninstalled by that copy."""
    import winreg
    folder = prefix() / "setup"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "VPNGo-Setup.exe"
    if setup_exe and Path(setup_exe).resolve() != target.resolve():
        shutil.copy2(setup_exe, target)
    icon = folder / "vpngo.ico"
    bundled = Path(__file__).resolve().parent / "vpngo.ico"
    if bundled.is_file():
        shutil.copy2(bundled, icon)
    values = {
        "DisplayName": "VPNGo" if gui else "vpngo", "DisplayVersion": version, "Publisher": "GustavoHSCruz",
        "DisplayIcon": str(icon), "InstallLocation": str(prefix()),
        "UninstallString": f'"{target}" --uninstall', "QuietUninstallString": f'"{target}" --uninstall --silent',
        "URLInfoAbout": f"https://github.com/{REPOSITORY}", "Mode": "gui" if gui else "cli",
    }
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY) as handle:
        for name, value in values.items():
            winreg.SetValueEx(handle, name, 0, winreg.REG_SZ, value)
        for name in ("NoModify", "NoRepair"):
            winreg.SetValueEx(handle, name, 0, winreg.REG_DWORD, 1)


def installed_mode():
    """'gui' or 'cli' from the last install, or None when VPNGo Setup has not installed vpngo."""
    return registry_value(UNINSTALL_KEY, "Mode")


# --- Uninstall ---------------------------------------------------------------------------

def remove_user_path(folder):
    import winreg
    stored = registry_value("Environment", "Path") or ""
    kept = [part for part in stored.split(";") if part and part.rstrip("\\").lower() != str(folder).rstrip("\\").lower()]
    if ";".join(kept) != stored:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_SET_VALUE) as handle:
            winreg.SetValueEx(handle, "Path", 0, winreg.REG_EXPAND_SZ, ";".join(kept))


def uninstall(log):
    import winreg
    stop_gui(log)
    bin_folder = Path.home() / "bin"
    if shortcut().exists():
        root = gui_root()
        for name in ("app", "venv", "engine"):
            shutil.rmtree(root / name, ignore_errors=True)
        for path in (root / "cli.json", bin_folder / "vpngo-gui.cmd", shortcut()):
            path.unlink(missing_ok=True)
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0,
                                winreg.KEY_SET_VALUE) as handle:
                winreg.DeleteValue(handle, "VPNGo")
        except OSError:
            pass
        log("The interface was removed; its history and settings are kept.")
    (bin_folder / "vpngo.cmd").unlink(missing_ok=True)
    for backup in bin_folder.glob("vpngo.cmd.backup.*"):
        backup.unlink(missing_ok=True)
    # mihomo.exe and other tools may share the folder; it leaves PATH only when empty.
    if bin_folder.is_dir() and not any(bin_folder.iterdir()):
        remove_user_path(bin_folder)
    for name in ("app", "app.new", "app.old"):
        shutil.rmtree(prefix() / name, ignore_errors=True)
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY)
    except OSError:
        pass
    log("vpngo was removed; profiles and settings are kept.")


def remove_setup_copy():
    """The running copy cannot delete itself; cmd removes it once this process has exited."""
    folder = prefix() / "setup"
    subprocess.Popen(f'cmd /c ping -n 3 127.0.0.1 >nul & rmdir /s /q "{folder}"', creationflags=NO_WINDOW,
                     close_fds=True)


# --- The whole run -----------------------------------------------------------------------

class Events:
    """What a run reports. The window and the silent mode override these."""

    def step(self, name, state):            # state: running, done, skipped or failed
        pass

    def progress(self, name, fraction):
        pass

    def log(self, line):
        pass


def steps(gui, proxifyre):
    """The step names an install goes through, in order."""
    return ["python", "download", "files", "command"] + (["gui"] if gui else []) + \
        (["proxifyre"] if proxifyre else []) + ["finish"]


def install(gui, proxifyre, events, setup_exe=None):
    """Install or upgrade. Returns 0, or raises SetupError with the exit code to report."""
    current = None

    def begin(name):
        nonlocal current
        if current:
            events.step(current, "done")
        current = name
        events.step(name, "running")

    try:
        begin("python")
        check_other_installers(events.log)
        interpreter = python()
        if interpreter:
            events.log(f"Using Python at {interpreter}.")
        else:
            events.log("Python 3 was not found; installing it for this user with winget...")
            install_python(events.log)
            interpreter = python()
        begin("download")
        version = latest_version()
        events.log(f"Downloading vpngo {version}...")
        archive = download(version, lambda done, total: events.progress("download", done / total))
        events.log("Checksum verified.")
        begin("files")
        install_files(archive, version, events.log)
        begin("command")
        try:
            install_command(version, interpreter, events.log)
        except SetupError:
            restore_previous()
            raise
        # Listed in Settings > Apps from here on, so a failed optional step can still be undone.
        register(version, setup_exe, False)
        if gui:
            begin("gui")
            install_gui(events.log)
            register(version, setup_exe, True)
        if proxifyre:
            begin("proxifyre")
            install_proxifyre(events.log)
        begin("finish")
        events.step("finish", "done")
        return 0
    except SetupError as error:
        events.log(str(error))
        if current:
            events.step(current, "failed")
        raise
    except Exception as error:  # Anything unexpected still ends the run with a message and code 1.
        events.log(f"{type(error).__name__}: {error}")
        if current:
            events.step(current, "failed")
        raise SetupError(str(error)) from error
