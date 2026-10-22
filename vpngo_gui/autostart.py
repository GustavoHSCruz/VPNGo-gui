"""Start the interface (in the tray, window hidden) when the user logs in.

Linux: an XDG autostart entry. macOS: a LaunchAgent. Windows: the user's Run key.
Each one runs this same Python and run.py, so it follows the installed copy.
"""

import os
import plistlib
import sys
from pathlib import Path


LABEL = "br.dev.gcruz.vpngo-gui"


def command():
    python = Path(sys.executable)
    if os.name == "nt" and python.with_name("pythonw.exe").is_file():
        python = python.with_name("pythonw.exe")  # No console window at login.
    return [str(python), str(Path(__file__).resolve().parent.parent / "run.py"), "--hidden"]


def desktop_quote(argument):
    """Desktop entries quote with double quotes and escape ", `, $ and \\ inside them."""
    if argument and not any(character in argument for character in " \t\n\"'\\><~|&;$*?#()`"):
        return argument
    return '"' + "".join("\\" + c if c in '"`$\\' else c for c in argument) + '"'


def linux_entry():
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "autostart/vpngo-gui.desktop"


def mac_agent():
    return Path.home() / "Library/LaunchAgents" / f"{LABEL}.plist"


def enabled():
    if os.name == "nt":
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run") as key:
                winreg.QueryValueEx(key, "VPNGo")
            return True
        except OSError:
            return False
    return (mac_agent() if sys.platform == "darwin" else linux_entry()).is_file()


def set_enabled(on):
    if os.name == "nt":
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0,
                            winreg.KEY_SET_VALUE) as key:
            if on:
                winreg.SetValueEx(key, "VPNGo", 0, winreg.REG_SZ, " ".join(f'"{part}"' for part in command()))
            else:
                try:
                    winreg.DeleteValue(key, "VPNGo")
                except FileNotFoundError:
                    pass
        return
    path = mac_agent() if sys.platform == "darwin" else linux_entry()
    if not on:
        path.unlink(missing_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    if sys.platform == "darwin":
        path.write_bytes(plistlib.dumps({"Label": LABEL, "ProgramArguments": command(), "RunAtLoad": True}))
    else:
        line = " ".join(desktop_quote(part) for part in command())
        icon = Path(__file__).resolve().parent / "assets/vpngo.svg"
        path.write_text(f"[Desktop Entry]\nType=Application\nName=VPNGo\nExec={line}\nIcon={icon}\n"
                        "X-GNOME-Autostart-enabled=true\n", encoding="utf-8")
