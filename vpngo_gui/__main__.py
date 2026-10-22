"""vpngo-gui [--hidden] | --version | --askpass <prompt>  (run.py starts it)"""

import sys

from . import version


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if args[:1] == ["--version"]:
        print(f"vpngo-gui {version()}")
        return 0
    if args[:1] == ["--askpass"]:
        from .askpass import client
        return client(" ".join(args[1:]))
    if args not in ([], ["--hidden"]):
        print("Usage: vpngo-gui [--hidden]", file=sys.stderr)
        return 2
    from .app import main as run
    return run(hidden=args == ["--hidden"])


if __name__ == "__main__":
    sys.exit(main())
