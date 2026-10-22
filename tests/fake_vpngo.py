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
    groups = data.setdefault("groups", {})
    if args == ["status", "--json"]:
        for app in data["apps"]:
            app["group"] = next((group for group, members in groups.items() if app["name"] in members), None)
        print(json.dumps({"schema": 1, "version": "test", "platform": "linux",
                          "profiles": data["profiles"], "apps": data["apps"],
                          "groups": [{"name": name, "apps": members} for name, members in groups.items()]}))
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
    elif command in {"--temp", "--install-gui"}:
        pass
    elif command in {"switch", "assign"}:
        apps[name]["profile"] = args[2]
        if command == "switch":
            apps[name]["active_profile"] = args[2]
    elif command == "profile" and args[1] == "remove":
        data["profiles"].remove(args[2])
    elif command == "profile":
        data["profiles"] = sorted(set(data["profiles"]) | {args[2]})
    elif command == "group" and args[1] == "add":
        for members in groups.values():
            for app in args[3:]:
                if app in members:
                    members.remove(app)
        groups.setdefault(args[2], []).extend(args[3:])
    elif command == "group" and args[1] == "rename":
        data["groups"] = {args[3] if name == args[2] else name: members for name, members in groups.items()}
    elif command == "group" and args[1] == "remove":
        if args[3:]:
            groups[args[2]] = [app for app in groups[args[2]] if app not in args[3:]]
        if not args[3:] or not groups[args[2]]:
            del groups[args[2]]
    elif command == "group":
        for app in groups[args[2]]:
            if args[1] == "on":
                apps[app].update(state="vpn", active_profile=apps[app]["profile"])
            elif args[1] == "off" and apps[app]["state"] == "vpn":
                apps[app]["state"] = "direct"
            elif args[1] == "stop":
                apps[app].update(state="stopped", active_profile=None)
    elif command == "policy":
        apps[name][args[2]] = args[3] == "on"
    elif command == "app":
        data["apps"] = [app for app in data["apps"] if app["name"] != args[2]]
    elif command == "config":
        pass
    STATE.write_text(json.dumps(data))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
