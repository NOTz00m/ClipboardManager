from __future__ import annotations

import datetime
import os
import sqlite3
from collections.abc import Callable, Iterable


class DatabaseManager:
    TAG_COLORS = (
        "#EF4444", "#F59E0B", "#10B981", "#3B82F6",
        "#8B5CF6", "#EC4899", "#14B8A6", "#F97316",
    )

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path, timeout=10)
        self.conn.execute("pragma journal_mode = wal")
        self.conn.execute("pragma synchronous = normal")
        self.conn.execute("pragma busy_timeout = 10000")
        self.conn.execute("pragma foreign_keys = on")
        self.create_tables()

    def create_tables(self) -> None:
        with self.conn:
            self.conn.execute(
                """
                create table if not exists history (
                    id integer primary key autoincrement,
                    text blob not null,
                    timestamp text not null,
                    is_code integer not null default 0,
                    pinned integer not null default 0,
                    favorite integer not null default 0,
                    content_hash text
                )
                """
            )
            columns = {row[1] for row in self.conn.execute("pragma table_info(history)")}
            if "content_hash" not in columns:
                self.conn.execute("alter table history add column content_hash text")

            self.conn.execute(
                """
                create table if not exists snippets (
                    id integer primary key autoincrement,
                    title text not null,
                    text blob not null,
                    language text not null default 'Text',
                    timestamp text not null,
                    favorite integer not null default 0
                )
                """
            )
            self.conn.execute(
                """
                create table if not exists tags (
                    id integer primary key autoincrement,
                    name text unique not null,
                    color text not null default '#6B7280'
                )
                """
            )
            self.conn.execute(
                """
                create table if not exists entry_tags (
                    id integer primary key autoincrement,
                    entry_id integer not null,
                    tag_id integer not null,
                    entry_type text not null default 'history'
                        check (entry_type in ('history', 'snippet')),
                    unique(entry_id, tag_id, entry_type)
                )
                """
            )
            self.conn.execute("create index if not exists idx_history_sort on history(pinned desc, timestamp desc, id desc)")
            self.conn.execute("create index if not exists idx_history_hash on history(content_hash)")
            self.conn.execute("create index if not exists idx_entry_tags_tag on entry_tags(tag_id, entry_type, entry_id)")
            self.conn.execute("create index if not exists idx_entry_tags_entry on entry_tags(entry_id, entry_type)")

    # History -------------------------------------------------------------

    def reconcile_content_hashes(
        self,
        decrypt: Callable[[bytes | str], str],
        fingerprint: Callable[[str], str],
    ) -> int:
        # deduplicate old rows using content hash
        rows = self.conn.execute(
            "select id, text, timestamp, pinned, favorite from history order by timestamp desc, id desc"
        ).fetchall()
        seen: dict[str, int] = {}
        merged = 0
        with self.conn:
            for entry_id, encrypted_text, _timestamp, pinned, favorite in rows:
                plain_text = decrypt(encrypted_text)
                if plain_text == "":
                    continue
                content_hash = fingerprint(plain_text)
                keeper_id = seen.get(content_hash)
                if keeper_id is None:
                    existing = self.conn.execute(
                        "select id from history where content_hash = ? and id <> ? order by timestamp desc, id desc limit 1",
                        (content_hash, entry_id),
                    ).fetchone()
                    if existing:
                        keeper_id = existing[0]
                        seen[content_hash] = keeper_id
                    else:
                        self.conn.execute(
                            "update history set content_hash = ? where id = ?",
                            (content_hash, entry_id),
                        )
                        seen[content_hash] = entry_id
                        continue

                if keeper_id == entry_id:
                    continue
                self._merge_history_rows(keeper_id, entry_id, pinned, favorite)
                merged += 1

            self.conn.execute(
                "create unique index if not exists uq_history_content_hash on history(content_hash) where content_hash is not null"
            )
        return merged

    def _merge_history_rows(self, keeper_id: int, duplicate_id: int, pinned: int = 0, favorite: int = 0) -> None:
        self.conn.execute(
            "update history set pinned = max(pinned, ?), favorite = max(favorite, ?) where id = ?",
            (pinned, favorite, keeper_id),
        )
        self.conn.execute(
            """
            insert or ignore into entry_tags (entry_id, tag_id, entry_type)
            select ?, tag_id, 'history' from entry_tags
            where entry_id = ? and entry_type = 'history'
            """,
            (keeper_id, duplicate_id),
        )
        self.conn.execute(
            "delete from entry_tags where entry_id = ? and entry_type = 'history'",
            (duplicate_id,),
        )
        self.conn.execute("delete from history where id = ?", (duplicate_id,))

    def store_entry(
        self,
        encrypted_text: bytes | str,
        timestamp: str,
        is_code_flag: int,
        content_hash: str,
    ) -> tuple[int, bool]:
        # insert or move existing match to top
        with self.conn:
            existing = self.conn.execute(
                "select id from history where content_hash = ?", (content_hash,)
            ).fetchone()
            if existing:
                entry_id = existing[0]
                self.conn.execute(
                    "update history set text = ?, timestamp = ?, is_code = ? where id = ?",
                    (encrypted_text, timestamp, int(bool(is_code_flag)), entry_id),
                )
                return entry_id, False
            try:
                cursor = self.conn.execute(
                    """
                    insert into history (text, timestamp, is_code, pinned, favorite, content_hash)
                    values (?, ?, ?, 0, 0, ?)
                    """,
                    (encrypted_text, timestamp, int(bool(is_code_flag)), content_hash),
                )
                return int(cursor.lastrowid), True
            except sqlite3.IntegrityError:
                row = self.conn.execute(
                    "select id from history where content_hash = ?", (content_hash,)
                ).fetchone()
                if row is None:
                    raise
                self.conn.execute(
                    "update history set text = ?, timestamp = ?, is_code = ? where id = ?",
                    (encrypted_text, timestamp, int(bool(is_code_flag)), row[0]),
                )
                return int(row[0]), False

    def add_entry(self, encrypted_text, timestamp, is_code_flag, content_hash=None):
        if content_hash:
            return self.store_entry(encrypted_text, timestamp, is_code_flag, content_hash)[0]
        with self.conn:
            cursor = self.conn.execute(
                "insert into history (text, timestamp, is_code, pinned, favorite) values (?, ?, ?, 0, 0)",
                (encrypted_text, timestamp, int(bool(is_code_flag))),
            )
            return int(cursor.lastrowid)

    def get_all_entries(self, limit: int | None = None, offset: int = 0):
        sql = "select id, text, timestamp, is_code, pinned, favorite from history order by pinned desc, timestamp desc, id desc"
        params: tuple[int, ...] = ()
        if limit is not None:
            sql += " limit ? offset ?"
            params = (max(0, int(limit)), max(0, int(offset)))
        return self.conn.execute(sql, params).fetchall()

    def count_history(self) -> int:
        return int(self.conn.execute("select count(*) from history").fetchone()[0])

    def get_saved_history_entries(self):
        return self.conn.execute(
            """
            select id, text, timestamp, is_code, pinned, favorite from history
            where pinned = 1 or favorite = 1
            order by pinned desc, timestamp desc, id desc
            """
        ).fetchall()

    def get_entry_by_id(self, entry_id):
        return self.conn.execute(
            "select text, pinned, favorite from history where id = ?", (entry_id,)
        ).fetchone()

    def update_pin_state(self, entry_id, new_state):
        with self.conn:
            self.conn.execute("update history set pinned = ? where id = ?", (int(bool(new_state)), entry_id))

    def update_favorite_state(self, entry_id, new_state):
        with self.conn:
            self.conn.execute("update history set favorite = ? where id = ?", (int(bool(new_state)), entry_id))

    def delete_entries_older_than(self, cutoff_timestamp):
        with self.conn:
            self.conn.execute(
                "delete from entry_tags where entry_type = 'history' and entry_id in (select id from history where timestamp < ?)",
                (cutoff_timestamp,),
            )
            self.conn.execute("delete from history where timestamp < ?", (cutoff_timestamp,))

    def delete_entry_by_id(self, entry_id):
        with self.conn:
            self.conn.execute(
                "delete from entry_tags where entry_id = ? and entry_type = 'history'", (entry_id,)
            )
            self.conn.execute("delete from history where id = ?", (entry_id,))

    def clear_history(self):
        with self.conn:
            self.conn.execute("delete from entry_tags where entry_type = 'history'")
            self.conn.execute("delete from history")

    def update_entry_text(self, entry_id, new_encrypted_text):
        with self.conn:
            self.conn.execute("update history set text = ? where id = ?", (new_encrypted_text, entry_id))

    def update_entry_content(self, entry_id, encrypted_text, content_hash, is_code_flag):
        with self.conn:
            duplicate = self.conn.execute(
                "select id from history where content_hash = ? and id <> ?", (content_hash, entry_id)
            ).fetchone()
            if duplicate:
                state = self.conn.execute(
                    "select pinned, favorite from history where id = ?", (entry_id,)
                ).fetchone() or (0, 0)
                self._merge_history_rows(duplicate[0], entry_id, state[0], state[1])
                return int(duplicate[0])
            self.conn.execute(
                "update history set text = ?, content_hash = ?, is_code = ? where id = ?",
                (encrypted_text, content_hash, int(bool(is_code_flag)), entry_id),
            )
            return int(entry_id)

    def reencrypt_payloads(self, transform: Callable[[bytes | str], bytes | str]):
        history_updates = [
            (transform(payload), entry_id)
            for entry_id, payload in self.conn.execute("select id, text from history").fetchall()
        ]
        snippet_updates = [
            (transform(payload), snippet_id)
            for snippet_id, payload in self.conn.execute("select id, text from snippets").fetchall()
        ]
        with self.conn:
            self.conn.executemany("update history set text = ? where id = ?", history_updates)
            self.conn.executemany("update snippets set text = ? where id = ?", snippet_updates)

    # Snippets ------------------------------------------------------------

    def add_snippet(self, title, encrypted_text, language="Text", timestamp=None):
        timestamp = timestamp or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.conn:
            cursor = self.conn.execute(
                "insert into snippets (title, text, language, timestamp, favorite) values (?, ?, ?, ?, 0)",
                (title, encrypted_text, language, timestamp),
            )
            return int(cursor.lastrowid)

    def get_all_snippets(self):
        return self.conn.execute(
            "select id, title, text, language, timestamp, favorite from snippets order by timestamp desc, id desc"
        ).fetchall()

    def get_favorite_snippets(self):
        return self.conn.execute(
            """
            select id, title, text, language, timestamp, favorite from snippets
            where favorite = 1 order by timestamp desc, id desc
            """
        ).fetchall()

    def get_snippet_by_id(self, snippet_id):
        return self.conn.execute(
            "select id, title, text, language, timestamp, favorite from snippets where id = ?",
            (snippet_id,),
        ).fetchone()

    def update_snippet(self, snippet_id, title=None, encrypted_text=None, language=None):
        updates = []
        values = []
        for column, value in (("title", title), ("text", encrypted_text), ("language", language)):
            if value is not None:
                updates.append(f"{column} = ?")
                values.append(value)
        if not updates:
            return
        values.append(snippet_id)
        with self.conn:
            self.conn.execute(f"update snippets set {', '.join(updates)} where id = ?", values)

    def update_snippet_favorite(self, snippet_id, new_state):
        with self.conn:
            self.conn.execute(
                "update snippets set favorite = ? where id = ?", (int(bool(new_state)), snippet_id)
            )

    def delete_snippet_by_id(self, snippet_id):
        with self.conn:
            self.conn.execute(
                "delete from entry_tags where entry_id = ? and entry_type = 'snippet'", (snippet_id,)
            )
            self.conn.execute("delete from snippets where id = ?", (snippet_id,))

    # Tags ----------------------------------------------------------------

    def add_tag(self, name, color=None):
        name = " ".join(str(name).strip().split())[:40]
        if not name:
            return None
        existing = self.conn.execute(
            "select id from tags where name = ? collate nocase", (name,)
        ).fetchone()
        if existing:
            return int(existing[0])
        if color is None:
            count = self.conn.execute("select count(*) from tags").fetchone()[0]
            color = self.TAG_COLORS[count % len(self.TAG_COLORS)]
        try:
            with self.conn:
                cursor = self.conn.execute("insert into tags (name, color) values (?, ?)", (name, color))
                return int(cursor.lastrowid)
        except sqlite3.IntegrityError:
            row = self.conn.execute(
                "select id from tags where name = ? collate nocase", (name,)
            ).fetchone()
            return int(row[0]) if row else None

    def get_all_tags(self):
        return self.conn.execute("select id, name, color from tags order by name collate nocase").fetchall()

    def get_tag_by_name(self, name):
        return self.conn.execute(
            "select id, name, color from tags where name = ? collate nocase", (name,)
        ).fetchone()

    def delete_tag(self, tag_id):
        with self.conn:
            self.conn.execute("delete from entry_tags where tag_id = ?", (tag_id,))
            self.conn.execute("delete from tags where id = ?", (tag_id,))

    def get_tag_counts(self):
        return self.conn.execute(
            """
            select t.id, t.name, t.color, count(et.id) as cnt
            from tags t left join entry_tags et on t.id = et.tag_id
            group by t.id order by cnt desc, t.name collate nocase
            """
        ).fetchall()

    def tag_entry(self, entry_id, tag_id, entry_type="history"):
        with self.conn:
            self.conn.execute(
                "insert or ignore into entry_tags (entry_id, tag_id, entry_type) values (?, ?, ?)",
                (entry_id, tag_id, entry_type),
            )

    def untag_entry(self, entry_id, tag_id, entry_type="history"):
        with self.conn:
            self.conn.execute(
                "delete from entry_tags where entry_id = ? and tag_id = ? and entry_type = ?",
                (entry_id, tag_id, entry_type),
            )

    def set_tags_for_entry(self, entry_id: int, tag_ids: Iterable[int], entry_type="history"):
        wanted = {int(tag_id) for tag_id in tag_ids}
        with self.conn:
            current = {
                row[0]
                for row in self.conn.execute(
                    "select tag_id from entry_tags where entry_id = ? and entry_type = ?",
                    (entry_id, entry_type),
                )
            }
            for tag_id in current - wanted:
                self.conn.execute(
                    "delete from entry_tags where entry_id = ? and tag_id = ? and entry_type = ?",
                    (entry_id, tag_id, entry_type),
                )
            for tag_id in wanted - current:
                self.conn.execute(
                    "insert or ignore into entry_tags (entry_id, tag_id, entry_type) values (?, ?, ?)",
                    (entry_id, tag_id, entry_type),
                )

    def get_tags_for_entry(self, entry_id, entry_type="history"):
        return self.conn.execute(
            """
            select t.id, t.name, t.color from tags t
            join entry_tags et on t.id = et.tag_id
            where et.entry_id = ? and et.entry_type = ?
            order by t.name collate nocase
            """,
            (entry_id, entry_type),
        ).fetchall()

    def get_entries_by_tag(self, tag_id):
        return self.conn.execute(
            "select entry_id, entry_type from entry_tags where tag_id = ?", (tag_id,)
        ).fetchall()

    def get_history_entries_by_tag(self, tag_id):
        return self.conn.execute(
            """
            select h.id, h.text, h.timestamp, h.is_code, h.pinned, h.favorite
            from history h join entry_tags et
              on h.id = et.entry_id and et.entry_type = 'history'
            where et.tag_id = ?
            order by h.pinned desc, h.timestamp desc, h.id desc
            """,
            (tag_id,),
        ).fetchall()

    def get_snippets_by_tag(self, tag_id):
        return self.conn.execute(
            """
            select s.id, s.title, s.text, s.language, s.timestamp, s.favorite
            from snippets s join entry_tags et
              on s.id = et.entry_id and et.entry_type = 'snippet'
            where et.tag_id = ?
            order by s.timestamp desc, s.id desc
            """,
            (tag_id,),
        ).fetchall()

    def close(self):
        self.conn.close()


class ArchiveDatabaseManager:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path, timeout=10)
        self.conn.execute(
            """
            create table if not exists archive_history (
                id integer primary key autoincrement,
                text blob, timestamp text, is_code integer,
                pinned integer default 0, favorite integer default 0
            )
            """
        )
        self.conn.commit()

    def add_entries(self, entries):
        with self.conn:
            self.conn.executemany(
                "insert into archive_history (text, timestamp, is_code, pinned, favorite) values (?, ?, ?, ?, ?)",
                [(entry[1], entry[2], entry[3], entry[4], entry[5]) for entry in entries],
            )

    def close(self):
        self.conn.close()


def manage_history(db_manager, settings, app_dir):
    mode = settings.get("history_management", "keep")
    try:
        threshold_days = max(1, int(settings.get("history_threshold_days", "30")))
    except (TypeError, ValueError):
        threshold_days = 30
    cutoff = (datetime.datetime.now() - datetime.timedelta(days=threshold_days)).strftime("%Y-%m-%d %H:%M:%S")
    if mode == "auto-delete":
        db_manager.delete_entries_older_than(cutoff)
    elif mode == "archive":
        entries = [entry for entry in db_manager.get_all_entries() if entry[2] < cutoff]
        if entries:
            archive = ArchiveDatabaseManager(os.path.join(app_dir, "clipboard_manager_archive.db"))
            try:
                archive.add_entries(entries)
            finally:
                archive.close()
            with db_manager.conn:
                ids = [entry[0] for entry in entries]
                db_manager.conn.executemany(
                    "delete from entry_tags where entry_id = ? and entry_type = 'history'",
                    [(entry_id,) for entry_id in ids],
                )
                db_manager.conn.executemany("delete from history where id = ?", [(entry_id,) for entry_id in ids])
