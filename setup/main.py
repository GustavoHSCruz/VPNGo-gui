"""VPNGo Setup: installs vpngo and its interface on Windows, with a window or silently.

    VPNGo-Setup.exe                         the window: choose the app or only the command
    VPNGo-Setup.exe --silent                vpngo and the interface, no window
    VPNGo-Setup.exe --silent --cli-only     only the vpngo command
    VPNGo-Setup.exe --with-proxifyre        with --silent: also install ProxiFyre (asks for admin)
    VPNGo-Setup.exe --uninstall [--silent]  remove vpngo and the interface; settings are kept

Exit codes: 0 done; 1 failed before vpngo was installed; 10 the vpngo command failed;
11 ProxiFyre failed; 12 the interface failed; 13 Python could not be installed. A silent run
writes its log to %TEMP%\\VPNGo-Setup.log.
"""

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent)]  # setup\ and the interface's own vpngo_gui package.

import installer  # noqa: E402

VERSION = "dev"


def setup_exe():
    """The .exe this runs from (Nuitka's onefile binary), copied beside vpngo as its uninstaller."""
    path = Path(sys.argv[0]).resolve()
    return str(path) if path.suffix.lower() == ".exe" else None


class LogFile(installer.Events):
    def __init__(self, path):
        self.file = open(path, "w", encoding="utf-8")

    def step(self, name, state):
        self.log(f"[{name}] {state}")

    def log(self, line):
        self.file.write(line + "\n")
        self.file.flush()


def silent(arguments):
    events = LogFile(Path(os.environ.get("TEMP") or ".") / "VPNGo-Setup.log")
    try:
        if "--uninstall" in arguments:
            installer.uninstall(events.log)
            installer.remove_setup_copy()
        else:
            installer.install("--cli-only" not in arguments, "--with-proxifyre" in arguments, events, setup_exe())
        return 0
    except installer.SetupError as error:
        events.log(str(error))
        return error.code


def window(arguments):
    from PySide6.QtWidgets import QApplication
    from vpngo_gui import theme
    from ui import SetupWindow
    application = QApplication(sys.argv[:1])
    application.setStyle("Fusion")
    theme.load_fonts()
    application.setFont(theme.font(14))
    application.setPalette(theme.palette())
    application.setStyleSheet(theme.STYLE)
    setup = SetupWindow(uninstall="--uninstall" in arguments, setup_exe=setup_exe())
    setup.show()
    application.exec()
    return setup.exit_code


def main():
    arguments = sys.argv[1:]
    if "--version" in arguments:
        print(f"VPNGo Setup {VERSION}")
        return 0
    return silent(arguments) if "--silent" in arguments else window(arguments)


if __name__ == "__main__":
    sys.exit(main())
