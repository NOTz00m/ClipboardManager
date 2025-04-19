import os
import sqlite3
import datetime

class DatabaseManager:
    def __init__(self, db_path):
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path)
        self.create_table()

    def create_table(self):
        c = self.conn.cursor()
        c.execute('''
            create table if not exists history (
                id integer primary key autoincrement,
                text blob,
                timestamp text,
                is_code integer,
                pinned integer default 0,
                favorite integer default 0
            )
        ''')
        self.conn.commit()

    def add_entry(self, encrypted_text, timestamp, is_code_flag):
        c = self.conn.cursor()
        c.execute(
            "insert into history (text, timestamp, is_code, pinned, favorite) values (?, ?, ?, 0, 0)",
            (encrypted_text, timestamp, is_code_flag)
        )
        self.conn.commit()

    def get_all_entries(self):
        c = self.conn.cursor()
        c.execute("select id, text, timestamp, is_code, pinned, favorite from history order by pinned desc, id desc")
        return c.fetchall()

    def get_entry_by_id(self, entry_id):
        c = self.conn.cursor()
        c.execute("select text, pinned, favorite from history where id=?", (entry_id,))
        return c.fetchone()

    def update_pin_state(self, entry_id, new_state):
        c = self.conn.cursor()
        c.execute("update history set pinned = ? where id = ?", (new_state, entry_id))
        self.conn.commit()

    def update_favorite_state(self, entry_id, new_state):
        c = self.conn.cursor()
        c.execute("update history set favorite = ? where id = ?", (new_state, entry_id))
        self.conn.commit()

    def delete_entries_older_than(self, cutoff_timestamp):
        c = self.conn.cursor()
        c.execute("delete from history where timestamp < ?", (cutoff_timestamp,))
        self.conn.commit()

    def delete_entry_by_id(self, entry_id):
        c = self.conn.cursor()
        c.execute("delete from history where id = ?", (entry_id,))
        self.conn.commit()

    def update_entry_text(self, entry_id, new_encrypted_text):
        c = self.conn.cursor()
        c.execute("update history set text = ? where id = ?", (new_encrypted_text, entry_id))
        self.conn.commit()

class ArchiveDatabaseManager:
    def __init__(self, db_path):
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path)
        self.create_table()

    def create_table(self):
        c = self.conn.cursor()
        c.execute('''
            create table if not exists archive_history (
                id integer primary key autoincrement,
                text blob,
                timestamp text,
                is_code integer,
                pinned integer default 0,
                favorite integer default 0
            )
        ''')
        self.conn.commit()

    def add_entry(self, entry):
        c = self.conn.cursor()
        c.execute(
            "insert into archive_history (text, timestamp, is_code, pinned, favorite) values (?, ?, ?, ?, ?)",
            (entry[1], entry[2], entry[3], entry[4], entry[5])
        )
        self.conn.commit()

def manage_history(db_manager, settings, app_dir):
    mode = settings.get("history_management", "keep")
    try:
        threshold_days = int(settings.get("history_threshold_days", "30"))
    except ValueError:
        threshold_days = 30
    cutoff = (datetime.datetime.now() - datetime.timedelta(days=threshold_days)).strftime("%Y-%m-%d %H:%M:%S")
    if mode == "auto-delete":
        db_manager.delete_entries_older_than(cutoff)
    elif mode == "archive":
        archive_db_path = os.path.join(app_dir, "clipboard_manager_archive.db")
        archive_db_manager = ArchiveDatabaseManager(archive_db_path)
        entries = db_manager.get_all_entries()
        for entry in entries:
            if entry[2] < cutoff:
                archive_db_manager.add_entry(entry)
                db_manager.delete_entry_by_id(entry[0]) 