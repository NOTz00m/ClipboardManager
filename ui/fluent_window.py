from PySide6.QtWidgets import (QApplication, QSystemTrayIcon, QMenu, QLabel,
                                QHBoxLayout, QWidget)
from PySide6.QtGui import QIcon, QAction
from PySide6.QtCore import QTimer, Qt, Signal
from qfluentwidgets import (MSFluentWindow, NavigationItemPosition,
                             FluentIcon, setTheme, Theme, setThemeColor,
                             isDarkTheme)

from ui.history_page import HistoryPage
from ui.snippets_page import SnippetsPage
from ui.pinned_page import PinnedPage
from ui.tags_page import TagsPage
from ui.settings_page import SettingsPage
from utils import get_app_font, get_system_theme
from content_detection import is_code
from encryption import content_fingerprint, encrypt_text, decrypt_text
from hotkeys import GlobalHotkeyManager
from plugins.plugin_manager import PluginManager
from notifications.notification_manager import NotificationManager

import os
import sys
import json
import datetime


class ClipboardManagerWindow(MSFluentWindow):
    # main window with fluent sidebar shell

    showRequested = Signal()

    def __init__(self, db_manager, fernet, settings, app_dir,
                 fingerprint_key, settings_encryption_key):
        super().__init__()
        self.db_manager = db_manager
        self.fernet = fernet
        self.settings = settings
        self.app_dir = app_dir
        self.fingerprint_key = fingerprint_key
        self.settings_encryption_key = settings_encryption_key
        self._allow_exit = False
        self.showRequested.connect(self._restore_from_tray)

        self.app_font = get_app_font(10, self.settings)
        self._apply_initial_theme()

        setThemeColor('#0078D4')

        self.plugin_manager = PluginManager(app_dir)
        self.notification_manager = NotificationManager(app_dir)

        self._setup_tray_icon()

        # monitor clipboard changes
        self.clipboard = QApplication.clipboard()
        initial_text = self.clipboard.text()
        self.last_clipboard_fingerprint = (
            content_fingerprint(initial_text, self.fingerprint_key) if initial_text else None
        )
        self.clipboard.dataChanged.connect(self._on_clipboard_change)

        self.sync_timer = QTimer()
        self.sync_timer.timeout.connect(self._auto_sync)
        self._setup_sync_timer()

        if self.settings.get('gdrive_enabled', False):
            QTimer.singleShot(2000, self._sync_from_gdrive)

        self._create_pages()
        self._setup_navigation()

        self.setWindowTitle("Clipboard Manager")
        self._set_initial_size()

        self._refresh_all_pages()
        self._setup_global_shortcut()

    def _set_initial_size(self):
        screen = QApplication.primaryScreen()
        if screen:
            avail = screen.availableGeometry()
            w = max(1000, int(avail.width() * 0.65))
            h = max(700, int(avail.height() * 0.75))
            self.resize(w, h)
            x = avail.x() + (avail.width() - w) // 2
            y = avail.y() + (avail.height() - h) // 2
            self.move(x, y)
        else:
            self.resize(1100, 750)
        self.setMinimumSize(750, 550)

    def _apply_initial_theme(self):
        theme = self.settings.get("theme", "system")
        if theme == "dark":
            setTheme(Theme.DARK)
        elif theme == "light":
            setTheme(Theme.LIGHT)
        else:
            system_theme = get_system_theme()
            if system_theme == "dark":
                setTheme(Theme.DARK)
            else:
                setTheme(Theme.LIGHT)

    def _create_pages(self):
        self.history_page = HistoryPage(self.db_manager, self.fernet, self)
        self.snippets_page = SnippetsPage(self.db_manager, self.fernet, self)
        self.pinned_page = PinnedPage(self.db_manager, self.fernet, self)
        self.tags_page = TagsPage(self.db_manager, self.fernet, self)
        self.settings_page = SettingsPage(
            self.settings, self.app_dir, self.plugin_manager,
            settings_encryption_key=self.settings_encryption_key,
            parent=self,
        )

        self.settings_page.settingsChanged.connect(self._on_settings_changed)
        self.settings_page.themeChanged.connect(self._on_theme_changed)
        self.settings_page.syncRequested.connect(self._sync_with_gdrive)
        self.settings_page.resetRequested.connect(self._reset_all_history)
        self.settings_page.factoryResetRequested.connect(self._factory_reset)

    def _setup_navigation(self):
        self.addSubInterface(
            self.history_page,
            FluentIcon.HISTORY,
            "History",
            position=NavigationItemPosition.TOP
        )
        self.addSubInterface(
            self.snippets_page,
            FluentIcon.CODE,
            "Snippets",
            position=NavigationItemPosition.TOP
        )
        self.addSubInterface(
            self.pinned_page,
            FluentIcon.PIN,
            "Pinned",
            position=NavigationItemPosition.TOP
        )
        self.addSubInterface(
            self.tags_page,
            FluentIcon.TAG,
            "Tags",
            position=NavigationItemPosition.TOP
        )
        self.addSubInterface(
            self.settings_page,
            FluentIcon.SETTING,
            "Settings",
            position=NavigationItemPosition.BOTTOM
        )

        self.stackedWidget.currentChanged.connect(self._on_page_changed)

    def _on_page_changed(self, index):
        current = self.stackedWidget.currentWidget()
        if hasattr(current, 'load_entries'):
            QTimer.singleShot(0, current.load_entries)

    def _refresh_all_pages(self):
        current = self.stackedWidget.currentWidget()
        if hasattr(current, "load_entries"):
            current.load_entries()

    def _setup_tray_icon(self):
        self.tray_icon = QSystemTrayIcon(self)

        if getattr(sys, 'frozen', False):
            icon_path = os.path.join(sys._MEIPASS, "clipboard.png")
        else:
            icon_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "clipboard.png"
            )

        if os.path.exists(icon_path):
            icon = QIcon(icon_path)
        else:
            icon = FluentIcon.PASTE.icon()

        self.tray_icon.setIcon(icon)
        self.setWindowIcon(icon)
        self.notification_manager.set_tray_icon(self.tray_icon)

        tray_menu = QMenu()

        restore_action = QAction("Show Window", self)
        restore_action.triggered.connect(self._restore_from_tray)
        tray_menu.addAction(restore_action)

        tray_menu.addSeparator()

        history_action = QAction("History", self)
        history_action.triggered.connect(lambda: self._show_page(self.history_page))
        tray_menu.addAction(history_action)

        snippets_action = QAction("Snippets", self)
        snippets_action.triggered.connect(lambda: self._show_page(self.snippets_page))
        tray_menu.addAction(snippets_action)

        settings_action = QAction("Settings", self)
        settings_action.triggered.connect(lambda: self._show_page(self.settings_page))
        tray_menu.addAction(settings_action)

        tray_menu.addSeparator()

        sync_action = QAction("Sync Now", self)
        sync_action.triggered.connect(self._sync_with_gdrive)
        tray_menu.addAction(sync_action)

        tray_menu.addSeparator()

        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self._exit_app)
        tray_menu.addAction(exit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()

    def _setup_global_shortcut(self):
        if not hasattr(self, "hotkey_manager"):
            self.hotkey_manager = GlobalHotkeyManager(self)
            self.hotkey_manager.activated.connect(self.showRequested.emit)
        shortcut = self.settings.get("global_shortcut", "ctrl+alt+v")
        success, error = self.hotkey_manager.bind(shortcut)
        if not success:
            self.tray_icon.showMessage(
                "Clipboard Manager",
                f"Could not register {shortcut}: {error}",
                QSystemTrayIcon.Warning,
                5000,
            )
        return success

    def _restore_from_tray(self):
        self.showNormal()
        self.setWindowState((self.windowState() & ~Qt.WindowMinimized) | Qt.WindowActive)
        self.raise_()
        self.activateWindow()
        QApplication.alert(self, 0)

    def _show_page(self, page):
        self._restore_from_tray()
        self.switchTo(page)

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self._restore_from_tray()

    def _on_clipboard_change(self, *args):
        text = self.clipboard.text()
        if text:
            incoming_fingerprint = content_fingerprint(text, self.fingerprint_key)
            if incoming_fingerprint == self.last_clipboard_fingerprint:
                return
            self.last_clipboard_fingerprint = incoming_fingerprint

            transformed_text = text
            for plugin in self.plugin_manager.get_enabled_plugins():
                if plugin.instance and hasattr(plugin.instance, 'on_clipboard_change'):
                    try:
                        result = plugin.instance.on_clipboard_change(transformed_text)
                        if isinstance(result, str) and result:
                            transformed_text = result
                    except Exception:
                        pass

            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            code_flag = is_code(transformed_text)
            encrypted_text = encrypt_text(transformed_text, self.fernet)
            final_fingerprint = content_fingerprint(transformed_text, self.fingerprint_key)
            self.db_manager.store_entry(
                encrypted_text, timestamp, code_flag, final_fingerprint
            )
            self.last_clipboard_fingerprint = final_fingerprint

            if self.stackedWidget.currentWidget() == self.history_page:
                QTimer.singleShot(0, self.history_page.load_entries)

            self.notification_manager.check_text(transformed_text)

            if transformed_text != text:
                self.copy_text(transformed_text)

    def copy_text(self, text):
        self.last_clipboard_fingerprint = content_fingerprint(text, self.fingerprint_key)
        self.clipboard.setText(text)

    def _setup_sync_timer(self):
        if self.settings.get('gdrive_enabled', False):
            self.sync_timer.start(5 * 60 * 1000)
        else:
            self.sync_timer.stop()

    def _sync_from_gdrive(self):
        if not self.settings.get('gdrive_enabled', False):
            return
        token_path = self.settings.get('gdrive_token', "")
        if not token_path:
            return
        try:
            from gdrive_sync import authenticate_gdrive, get_or_create_app_folder, download_file
            service = authenticate_gdrive(token_path)
            folder_id = get_or_create_app_folder(service)
            temp_file = os.path.join(self.app_dir, 'temp_sync.json')
            if download_file(temp_file, service, folder_id):
                with open(temp_file, 'r') as f:
                    sync_data = json.load(f)
                for entry in sync_data:
                    timestamp = entry['timestamp']
                    encrypted = entry['text'].encode() if isinstance(entry['text'], str) else entry['text']
                    plain = decrypt_text(encrypted, self.fernet)
                    if not plain:
                        continue
                    entry_id, _created = self.db_manager.store_entry(
                        encrypted,
                        timestamp,
                        entry['is_code'],
                        content_fingerprint(plain, self.fingerprint_key),
                    )
                    self.db_manager.update_pin_state(entry_id, entry.get('pinned', 0))
                    self.db_manager.update_favorite_state(entry_id, entry.get('favorite', 0))
                os.remove(temp_file)
                self._refresh_all_pages()
        except Exception:
            pass

    def _sync_with_gdrive(self):
        if not self.settings.get('gdrive_enabled', False):
            from qfluentwidgets import InfoBar
            InfoBar.warning("Sync", "Google Drive sync is not enabled.", parent=self)
            return
        token_path = self.settings.get('gdrive_token', "")
        if not token_path:
            from qfluentwidgets import InfoBar
            InfoBar.warning("Sync", "No token found. Authenticate first in Settings.", parent=self)
            return
        try:
            self._sync_from_gdrive()
            from gdrive_sync import authenticate_gdrive, get_or_create_app_folder, upload_file
            entries = self.db_manager.get_all_entries()
            sync_data = []
            for entry in entries:
                eid, enc_text, timestamp, is_code_flag, pinned, favorite = entry
                sync_data.append({
                    'text': enc_text.decode() if isinstance(enc_text, bytes) else enc_text,
                    'timestamp': timestamp, 'is_code': is_code_flag,
                    'pinned': pinned, 'favorite': favorite
                })
            temp_file = os.path.join(self.app_dir, 'temp_sync.json')
            with open(temp_file, 'w') as f:
                json.dump(sync_data, f)
            service = authenticate_gdrive(token_path)
            folder_id = get_or_create_app_folder(service)
            upload_file(temp_file, service, folder_id)
            os.remove(temp_file)
            from qfluentwidgets import InfoBar
            InfoBar.success("Sync", "Synced with Google Drive!", parent=self)
        except Exception as e:
            from qfluentwidgets import InfoBar
            InfoBar.error("Sync", f"Sync failed: {e}", parent=self)

    def _auto_sync(self):
        if self.settings.get('gdrive_enabled', False):
            self._sync_with_gdrive()

    def _reset_all_history(self):
        self.db_manager.clear_history()
        self._refresh_all_pages()

    def _factory_reset(self):
        if hasattr(self, "hotkey_manager"):
            self.hotkey_manager.close()
        self.db_manager.close()
        import shutil
        for item in os.listdir(self.app_dir):
            item_path = os.path.join(self.app_dir, item)
            if item == "clipboard_manager.lock":
                continue
            if os.path.isfile(item_path):
                try:
                    os.remove(item_path)
                except OSError:
                    pass
            elif os.path.isdir(item_path):
                shutil.rmtree(item_path, ignore_errors=True)
        self._allow_exit = True
        QApplication.quit()

    def _on_settings_changed(self, new_settings):
        self.settings = new_settings
        self._setup_sync_timer()
        self._setup_global_shortcut()
        self.app_font = get_app_font(10, self.settings)
        QApplication.instance().setFont(self.app_font)
        self._refresh_all_pages()

    def _on_theme_changed(self, theme):
        self.settings['theme'] = theme

    def closeEvent(self, event):
        if self._allow_exit:
            event.accept()
        else:
            event.ignore()
            self.hide()

    def _exit_app(self):
        self._allow_exit = True
        if hasattr(self, "hotkey_manager"):
            self.hotkey_manager.close()
        self.db_manager.close()
        self.tray_icon.hide()
        self.close()
        QApplication.quit()
