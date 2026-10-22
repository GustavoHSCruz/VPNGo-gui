"""VPNGo desktop interface: a tray app and window that drive the vpngo command line."""

from pathlib import Path


def version():
    """Release archives ship a VERSION file next to the package; a checkout reports dev."""
    path = Path(__file__).resolve().parent.parent / "VERSION"
    return path.read_text(encoding="utf-8").strip() if path.is_file() else "dev"
