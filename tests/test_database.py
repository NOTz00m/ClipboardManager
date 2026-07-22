import os
import tempfile
import unittest

from cryptography.fernet import Fernet

from database import DatabaseManager
from encryption import (DummyFernet, content_fingerprint, decrypt_text,
                        decrypt_text_strict, encrypt_text)


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db = DatabaseManager(os.path.join(self.temp_dir.name, "history.db"))
        self.fernet = DummyFernet()
        self.secret = b"unit-test-fingerprint-secret"

    def tearDown(self):
        self.db.close()
        self.temp_dir.cleanup()

    def fingerprint(self, text):
        return content_fingerprint(text, self.secret)

    def test_repeated_content_is_touched_not_duplicated(self):
        encrypted = encrypt_text("same text", self.fernet)
        first_id, created = self.db.store_entry(encrypted, "2026-01-01 10:00:00", 0, self.fingerprint("same text"))
        second_id, created_again = self.db.store_entry(encrypted, "2026-01-02 10:00:00", 0, self.fingerprint("same text"))

        self.assertTrue(created)
        self.assertFalse(created_again)
        self.assertEqual(first_id, second_id)
        self.assertEqual(self.db.count_history(), 1)
        self.assertEqual(self.db.get_all_entries()[0][2], "2026-01-02 10:00:00")

    def test_startup_reconciliation_merges_state_and_tags(self):
        older_id = self.db.add_entry(encrypt_text("duplicate", self.fernet), "2026-01-01 10:00:00", 0)
        newer_id = self.db.add_entry(encrypt_text("duplicate", self.fernet), "2026-01-02 10:00:00", 0)
        self.db.update_pin_state(older_id, 1)
        self.db.update_favorite_state(newer_id, 1)
        tag_id = self.db.add_tag("Important")
        self.db.tag_entry(older_id, tag_id)

        merged = self.db.reconcile_content_hashes(
            lambda value: decrypt_text(value, self.fernet), self.fingerprint
        )

        self.assertEqual(merged, 1)
        self.assertEqual(self.db.count_history(), 1)
        row = self.db.get_all_entries()[0]
        self.assertEqual(row[0], newer_id)
        self.assertEqual((row[4], row[5]), (1, 1))
        self.assertEqual(self.db.get_tags_for_entry(newer_id)[0][1], "Important")

    def test_existing_tags_are_case_insensitive_and_replaceable(self):
        first = self.db.add_tag("Work")
        second = self.db.add_tag("work")
        other = self.db.add_tag("Personal")
        entry_id, _ = self.db.store_entry(
            b"hello", "2026-01-01 10:00:00", 0, self.fingerprint("hello")
        )

        self.assertEqual(first, second)
        self.db.set_tags_for_entry(entry_id, [first, other])
        self.db.set_tags_for_entry(entry_id, [other])
        self.assertEqual([row[0] for row in self.db.get_tags_for_entry(entry_id)], [other])

    def test_editing_into_existing_content_merges_rows(self):
        first, _ = self.db.store_entry(b"one", "2026-01-01 10:00:00", 0, self.fingerprint("one"))
        second, _ = self.db.store_entry(b"two", "2026-01-02 10:00:00", 0, self.fingerprint("two"))
        self.db.update_pin_state(second, 1)

        retained = self.db.update_entry_content(second, b"one", self.fingerprint("one"), 0)

        self.assertEqual(retained, first)
        self.assertEqual(self.db.count_history(), 1)
        self.assertEqual(self.db.get_entry_by_id(first)[1], 1)

    def test_reencryption_validates_then_updates_history_and_snippets(self):
        old_fernet = Fernet(Fernet.generate_key())
        new_fernet = Fernet(Fernet.generate_key())
        entry_id = self.db.add_entry(encrypt_text("history", old_fernet), "2026-01-01 10:00:00", 0)
        snippet_id = self.db.add_snippet("Snippet", encrypt_text("snippet", old_fernet))

        self.db.reencrypt_payloads(
            lambda token: encrypt_text(decrypt_text_strict(token, old_fernet), new_fernet)
        )

        self.assertEqual(decrypt_text(self.db.get_entry_by_id(entry_id)[0], new_fernet), "history")
        self.assertEqual(decrypt_text(self.db.get_snippet_by_id(snippet_id)[2], new_fernet), "snippet")


if __name__ == "__main__":
    unittest.main()
