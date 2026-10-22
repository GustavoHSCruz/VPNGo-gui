#!/usr/bin/env python3
"""Build vpngo-gui-<version>.tar.gz and SHA256SUMS, the files `vpngo --install-gui` downloads.

The archive is reproducible: entries are sorted, owned by root and stamped with
the commit time (or SOURCE_DATE_EPOCH).
"""

import argparse
import gzip
import hashlib
import io
import os
import re
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INCLUDE = ("LICENSE", "README.md", "requirements.txt", "run.py", "vpngo_gui/")
VERSION_PATTERN = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?")


def tracked():
    names = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, check=True, capture_output=True).stdout
    return sorted(name for name in names.decode().split("\0")
                  if name and name.startswith(INCLUDE) and "__pycache__" not in name)


def archive(version, epoch):
    top = f"vpngo-gui-{version}"
    files = [(f"{top}/{name}", (ROOT / name).read_bytes()) for name in tracked()]
    files.append((f"{top}/VERSION", f"{version}\n".encode()))
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.PAX_FORMAT) as output:
        for name, data in sorted(files):
            info = tarfile.TarInfo(name)
            info.size, info.mtime, info.mode = len(data), epoch, 0o644
            info.uid = info.gid = 0
            info.uname = info.gname = "root"
            output.addfile(info, io.BytesIO(data))
    compressed = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=compressed, mtime=epoch, compresslevel=9) as output:
        output.write(buffer.getvalue())
    return f"{top}.tar.gz", compressed.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--out", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    if not VERSION_PATTERN.fullmatch(args.version):
        parser.error("version must look like 1.2.3 or 1.2.3-rc.1, without a leading v")
    epoch = int(os.environ.get("SOURCE_DATE_EPOCH") or
                subprocess.run(["git", "log", "-1", "--format=%ct"], cwd=ROOT, check=True,
                               capture_output=True, text=True).stdout.strip())
    args.out.mkdir(parents=True, exist_ok=True)
    name, data = archive(args.version, epoch)
    # The standalone installer is the engine module itself: it finds or downloads vpngo, then
    # has it install the interface.
    installer = (ROOT / "vpngo_gui/engine.py").read_bytes()
    assets = {name: data, "install.py": installer}
    lines = []
    for asset, content in sorted(assets.items()):
        (args.out / asset).write_bytes(content)
        lines.append(f"{hashlib.sha256(content).hexdigest()}  {asset}\n")
    (args.out / "SHA256SUMS").write_text("".join(lines), encoding="utf-8")
    print(f"Built {name}, install.py and SHA256SUMS in {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
