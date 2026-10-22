"""install.py / the engine: find vpngo on PATH, or download a verified private copy."""

import hashlib
import io
import json
import os
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from vpngo_gui import engine


def fake_vpngo(path, version_line):
    path.write_text(f"#!/bin/sh\n[ \"$1\" = version ] && echo '{version_line}' && exit 0\nexit 3\n")
    path.chmod(0o755)
    return path


@unittest.skipIf(os.name == "nt", "POSIX shell fixtures")
class EngineTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.mirror = self.root / "mirror"
        self.mirror.mkdir()
        environment = {"PATH": f"{self.bin}{os.pathsep}/usr/bin{os.pathsep}/bin",
                       "VPNGO_GUI_PREFIX": str(self.root / "gui"), "VPNGO_RELEASE_URL": self.mirror.as_uri(),
                       "VPNGO_VERSION": "0.6.0"}
        patcher = patch.dict(os.environ, environment)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.directory.cleanup)
        self.reports = []

    def publish(self, version="0.6.0", corrupt=False, reported=None):
        top = f"vpngo-{version}-{engine.system()}"
        launcher_name = f"{top}/{engine.system()}/vpngo"
        files = {f"{top}/shared/commands.py": ("", 0o644),
                 launcher_name: (f"#!/bin/sh\n[ \"$1\" = version ] && echo 'vpngo {reported or version}'\n", 0o755)}
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
            for name, (text, mode) in files.items():
                data = text.encode()
                info = tarfile.TarInfo(name)
                info.size, info.mode = len(data), mode
                archive.addfile(info, io.BytesIO(data))
        data = buffer.getvalue()
        asset = f"{top}.tar.gz"
        (self.mirror / asset).write_bytes(data + (b"x" if corrupt else b""))
        (self.mirror / "SHA256SUMS").write_text(f"{hashlib.sha256(data).hexdigest()}  {asset}\n")

    def test_versions(self):
        self.assertEqual(engine.parse_version("vpngo 0.6.0"), (0, 6, 0))
        self.assertEqual(engine.parse_version("vpngo 1.2.3-rc.1"), (1, 2, 3))
        self.assertIsNone(engine.parse_version("vpngo dev"))

    def test_a_compatible_vpngo_on_path_is_used_as_is(self):
        fake_vpngo(self.bin / "vpngo", "vpngo 0.6.0")
        self.assertEqual(engine.choose_engine(self.reports.append), [str(self.bin / "vpngo")])
        self.assertFalse((self.root / "gui/engine").exists())

    def test_a_source_checkout_counts_as_compatible(self):
        fake_vpngo(self.bin / "vpngo", "vpngo dev")
        self.assertEqual(engine.choose_engine(self.reports.append), [str(self.bin / "vpngo")])

    def test_missing_vpngo_downloads_a_verified_private_engine(self):
        self.publish()
        command = engine.choose_engine(self.reports.append)
        self.assertEqual(command, [str(self.root / f"gui/engine/app/{engine.system()}/vpngo")])
        self.assertEqual(engine.run_version(command), "vpngo 0.6.0")
        engine.record(command)
        self.assertEqual(json.loads((self.root / "gui/cli.json").read_text())["command"], command)
        self.assertEqual(engine.private_engine(), (command, "vpngo 0.6.0"))

    def test_too_old_vpngo_gets_a_private_engine_and_a_hint(self):
        fake_vpngo(self.bin / "vpngo", "vpngo 0.4.0")
        self.publish()
        command = engine.choose_engine(self.reports.append)
        self.assertIn("/gui/engine/app/", command[0])
        self.assertTrue(any("too old" in line for line in self.reports))

    def test_corrupt_download_installs_nothing(self):
        self.publish(corrupt=True)
        with self.assertRaisesRegex(engine.EngineError, "Checksum mismatch"):
            engine.download_engine(report=self.reports.append)
        self.assertFalse((self.root / "gui/engine/app").exists())

    def test_update_keeps_the_old_engine_if_the_new_one_does_not_start(self):
        self.publish("0.6.0")
        engine.download_engine(report=self.reports.append)
        self.publish("0.7.0", reported="broken")
        with self.assertRaisesRegex(engine.EngineError, "did not start"):
            engine.download_engine("0.7.0", report=self.reports.append)
        self.assertEqual(engine.private_engine()[1], "vpngo 0.6.0")


if __name__ == "__main__":
    unittest.main()
