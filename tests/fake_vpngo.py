#!/usr/bin/env python3
"""A stand-in vpngo for tests and screenshots: keeps state in $FAKE_VPNGO_STATE."""

import json
import os
import sys
from pathlib import Path

STATE = Path(os.environ["FAKE_VPNGO_STATE"])


def main(args):
    data = json.loads(STATE.read_text())
    log = data.setdefault("log", [])
    log.append(args)
    apps = {app["name"]: app for app in data["apps"]}
    if args == ["status", "--json"]:
        print(json.dumps({"schema": 1, "version": "test", "platform": "linux",
                          "profiles": data["profiles"], "apps": data["apps"]}))
        STATE.write_text(json.dumps(data))
        return 0
    if data.get("fail"):
        STATE.write_text(json.dumps(data))
        print(f"vpngo: {data['fail']}", file=sys.stderr)
        return 1
    command, name = args[0], args[1] if len(args) > 1 else None
    if command in {"on", "off"}:
        apps[name]["state"] = "vpn" if command == "on" else "direct"
    elif command == "start":
        apps[name].update(state="vpn", active_profile=apps[name]["profile"])
    elif command == "stop":
        apps[name].update(state="stopped", active_profile=None)
    elif command in {"switch", "assign"}:
        apps[name]["profile"] = args[2]
        if command == "switch":
            apps[name]["active_profile"] = args[2]
    elif command == "profile":
        data["profiles"] = sorted(set(data["profiles"]) | {args[2]})
    elif command == "config":
        pass
    STATE.write_text(json.dumps(data))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
