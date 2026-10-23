"""The update check reads release tags such as v0.4.0, without network access."""
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vpngo_gui import engine, updates


class LatestTest(unittest.TestCase):
    def test_reads_a_v_prefixed_tag(self):
        with patch.object(engine, "fetch", return_value=json.dumps({"tag_name": "v0.4.0"}).encode()):
            self.assertEqual(updates.latest("GustavoHSCruz/VPNGo-gui"), "0.4.0")

    def test_refuses_a_tag_without_a_version(self):
        with patch.object(engine, "fetch", return_value=json.dumps({"tag_name": "nightly"}).encode()):
            with self.assertRaises(engine.EngineError):
                updates.latest("GustavoHSCruz/VPNGo-gui")

    def test_offers_only_a_newer_version(self):
        self.assertTrue(updates.newer("0.4.0", "0.3.0"))
        self.assertFalse(updates.newer("0.3.0", "0.3.0"))


if __name__ == "__main__":
    unittest.main()
