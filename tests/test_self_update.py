from __future__ import annotations

import unittest

from enigmars_util.names import validate_verb
from enigmars_util.self_update import (
    UpdateError,
    UpdateStatus,
    parse_github_commit_json,
    parse_ls_remote,
    short_sha,
    validate_sha,
)


class SelfUpdateParseTest(unittest.TestCase):
    def test_ls_remote_main(self) -> None:
        text = (
            "e9bc17024a72c311a3c77fff66849e0a6f34ecf4\trefs/heads/main\n"
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\trefs/heads/dev\n"
        )
        self.assertEqual(
            parse_ls_remote(text),
            "e9bc17024a72c311a3c77fff66849e0a6f34ecf4",
        )

    def test_ls_remote_rejects_garbage(self) -> None:
        with self.assertRaises(UpdateError):
            parse_ls_remote("not-a-sha\trefs/heads/main")
        with self.assertRaises(UpdateError):
            parse_ls_remote("")
        with self.assertRaises(UpdateError):
            parse_ls_remote("e9bc17024a72c311a3c77fff66849e0a6f34ecf4;rm\trefs/heads/main")

    def test_github_json(self) -> None:
        sha = "e9bc17024a72c311a3c77fff66849e0a6f34ecf4"
        self.assertEqual(parse_github_commit_json(f'{{"sha": "{sha}", "commit": {{}}}}'), sha)
        with self.assertRaises(UpdateError):
            parse_github_commit_json('{"sha": "nope"}')
        with self.assertRaises(UpdateError):
            parse_github_commit_json("[1,2,3]")

    def test_validate_and_short(self) -> None:
        sha = "e9bc17024a72c311a3c77fff66849e0a6f34ecf4"
        self.assertEqual(validate_sha(" " + sha.upper() + " "), sha)
        self.assertEqual(short_sha(sha), "e9bc170")
        with self.assertRaises(UpdateError):
            validate_sha("../etc")
        with self.assertRaises(UpdateError):
            validate_sha("e9bc170")

    def test_status_available(self) -> None:
        local = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        remote = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
        st = UpdateStatus(local, remote, local != remote, "origin/main has new commits")
        self.assertTrue(st.available)
        self.assertEqual(validate_verb("self-update"), "self-update")


if __name__ == "__main__":
    unittest.main()
