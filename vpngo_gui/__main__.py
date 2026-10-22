"""vpngo-gui [--hidden] | --version | --update-engine | --askpass <prompt>  (run.py starts it)"""

import sys

from . import version


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if args[:1] == ["--version"]:
        print(f"vpngo-gui {version()}")
        return 0
    if args == ["--update-engine"]:
        from .engine import EngineError, download_engine, record
        try:
            record(download_engine())
        except EngineError as error:
            print(f"vpngo-gui: {error}", file=sys.stderr)
            return 1
        return 0
    if args[:1] == ["--askpass"]:
        from .askpass import client
        return client(" ".join(args[1:]))
    if args not in ([], ["--hidden"]):
        print("Usage: vpngo-gui [--hidden | --update-engine | --version]", file=sys.stderr)
        return 2
    from .app import main as run
    return run(hidden=args == ["--hidden"])


if __name__ == "__main__":
    sys.exit(main())
