import unittest

from shortcut_parser import parse_shortcut


class ShortcutParserTests(unittest.TestCase):
    def test_default_shortcut(self):
        modifiers, key = parse_shortcut("ctrl+alt+v")
        self.assertEqual(modifiers, {"ctrl", "alt"})
        self.assertEqual(key, "v")

    def test_aliases_and_function_keys(self):
        modifiers, key = parse_shortcut("Control + Shift + F10")
        self.assertEqual(modifiers, {"ctrl", "shift"})
        self.assertEqual(key, "f10")

    def test_rejects_multiple_non_modifier_keys(self):
        with self.assertRaises(ValueError):
            parse_shortcut("ctrl+a+b")


if __name__ == "__main__":
    unittest.main()
