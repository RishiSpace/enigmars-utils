from __future__ import annotations

import unittest

from enigmars_util.names import (
    validate_aur_helper,
    validate_package_list,
    validate_package_name,
    validate_search_query,
    validate_service,
    validate_verb,
)


class NamesTest(unittest.TestCase):
    def test_good_package(self) -> None:
        self.assertEqual(validate_package_name("linux-lts"), "linux-lts")
        self.assertEqual(validate_package_name("lib32-mesa"), "lib32-mesa")
        self.assertEqual(validate_package_name("foo@bar"), "foo@bar")

    def test_bad_package(self) -> None:
        for bad in ("", "-oops", "../etc", "foo;rm", "foo bar", "a/b", "x" * 200, "$(id)"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    validate_package_name(bad)

    def test_list_limit(self) -> None:
        with self.assertRaises(ValueError):
            validate_package_list([])
        with self.assertRaises(ValueError):
            validate_package_list(["a"] * 65)

    def test_verb_and_service(self) -> None:
        self.assertEqual(validate_verb("pkg-install"), "pkg-install")
        self.assertEqual(validate_verb("aur-helper-setup"), "aur-helper-setup")
        with self.assertRaises(ValueError):
            validate_verb("rm")
        self.assertEqual(validate_service("ufw"), "ufw")
        with self.assertRaises(ValueError):
            validate_service("sshd")
        self.assertEqual(validate_aur_helper("yay"), "yay")
        self.assertEqual(validate_aur_helper("paru"), "paru")
        with self.assertRaises(ValueError):
            validate_aur_helper("pikaur")
        with self.assertRaises(ValueError):
            validate_aur_helper("yay;id")

    def test_search_query(self) -> None:
        self.assertEqual(validate_search_query(" firefox "), "firefox")
        self.assertEqual(validate_search_query("foo;bar"), "")
        self.assertEqual(validate_search_query(""), "")


if __name__ == "__main__":
    unittest.main()
