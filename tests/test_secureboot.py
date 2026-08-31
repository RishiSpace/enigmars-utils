from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from enigmars_util.names import validate_verb
from enigmars_util.secureboot import (
    clear_resume,
    load_resume_phase,
    parse_sbctl_status,
    save_resume_phase,
)


class ParseStatusTest(unittest.TestCase):
    def test_json_from_sbctl(self) -> None:
        doc = {
            "installed": True,
            "guid": "ef362b5a-665f-4385-992e-5f444da5be25",
            "setup_mode": False,
            "secure_boot": True,
            "vendors": ["microsoft", "builtin-db"],
        }
        st = parse_sbctl_status(doc)
        self.assertTrue(st.uefi)
        self.assertTrue(st.sbctl_present)
        self.assertTrue(st.sbctl_installed)
        self.assertTrue(st.secure_boot)
        self.assertFalse(st.setup_mode)
        self.assertTrue(st.enrolled)
        self.assertTrue(st.microsoft_keys)
        self.assertEqual(st.guid, doc["guid"])

    def test_not_enrolled(self) -> None:
        st = parse_sbctl_status(
            {
                "installed": False,
                "guid": "",
                "setup_mode": True,
                "secure_boot": False,
                "vendors": [],
            }
        )
        self.assertFalse(st.sbctl_installed)
        self.assertTrue(st.setup_mode)
        self.assertFalse(st.secure_boot)
        self.assertFalse(st.enrolled)
        self.assertFalse(st.microsoft_keys)


class ResumeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self._old_state = os.environ.get("XDG_STATE_HOME")
        self._old_cfg = os.environ.get("XDG_CONFIG_HOME")
        os.environ["XDG_STATE_HOME"] = str(Path(self.tmp.name) / "state")
        os.environ["XDG_CONFIG_HOME"] = str(Path(self.tmp.name) / "config")

    def tearDown(self) -> None:
        def restore(key: str, old: str | None) -> None:
            if old is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old

        restore("XDG_STATE_HOME", self._old_state)
        restore("XDG_CONFIG_HOME", self._old_cfg)

    def test_roundtrip_and_reject(self) -> None:
        self.assertIsNone(load_resume_phase())
        save_resume_phase("enroll")
        self.assertEqual(load_resume_phase(), "enroll")
        save_resume_phase("enable-sb")
        self.assertEqual(load_resume_phase(), "enable-sb")
        with self.assertRaises(ValueError):
            save_resume_phase("rm-rf")
        clear_resume()
        self.assertIsNone(load_resume_phase())

    def test_helper_verbs(self) -> None:
        self.assertEqual(validate_verb("sbctl-enroll"), "sbctl-enroll")
        self.assertEqual(validate_verb("firmware-reboot"), "firmware-reboot")
        with self.assertRaises(ValueError):
            validate_verb("sbctl-reset")


if __name__ == "__main__":
    unittest.main()
