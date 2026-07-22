import json
import os
import tempfile
import unittest

from cryptography.fernet import Fernet

from settings import SettingsManager


class SettingsTests(unittest.TestCase):
    def test_personal_password_is_encrypted_and_round_trips(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "settings.json")
            key = Fernet.generate_key()
            settings = {
                "use_personal_key": True,
                "personal_key": "correct horse battery staple",
                "theme": "dark",
            }
            SettingsManager.save_settings(settings, path, key)

            with open(path, encoding="utf-8") as handle:
                raw = handle.read()
            self.assertNotIn("correct horse battery staple", raw)
            self.assertIn("enc:v1:", raw)
            loaded = SettingsManager.load_settings(path, key)
            self.assertEqual(loaded["personal_key"], settings["personal_key"])
            self.assertEqual(loaded["global_shortcut"], "ctrl+alt+v")

    def test_accidentally_plaintext_legacy_password_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "settings.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump({"use_personal_key": True, "personal_key": "legacy plaintext"}, handle)
            loaded = SettingsManager.load_settings(path, Fernet.generate_key())
            self.assertEqual(loaded["personal_key"], "legacy plaintext")


if __name__ == "__main__":
    unittest.main()
