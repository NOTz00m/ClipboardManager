from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QLineEdit, QTabWidget, QListWidget, QPlainTextEdit, QPushButton, QListWidgetItem, QApplication, QSystemTrayIcon, QMenu, QStyle, QDialog, QMessageBox, QHBoxLayout, QLabel, QCheckBox
from PySide6.QtGui import QIcon, QAction
from PySide6.QtCore import QTimer
from utils import get_app_font, get_system_theme, RAVENS_WING_DARK_STYLE, is_code, get_icon_path
from ui.history_item import HistoryItemWidget
from ui.settings_dialog import SettingsDialog
from encryption import encrypt_text, decrypt_text
import os
import sys
import datetime
import re
import json
from settings import SettingsManager
from gdrive_sync import authenticate_gdrive, get_or_create_app_folder, upload_file, download_file
from ui.plugin_settings_dialog import PluginSettingsDialog
from plugins.plugin_manager import PluginManager
from notifications.notification_manager import NotificationManager

class PluginTab(QWidget):
    def __init__(self, plugin_manager, parent=None):
        super().__init__(parent)
        self.plugin_manager = plugin_manager
        self.initUI()
        
    def initUI(self):
        layout = QVBoxLayout()
        
        self.plugin_list = QListWidget()
        self.plugin_list.setAlternatingRowColors(True)
        layout.addWidget(QLabel("Installed Plugins:"))
        layout.addWidget(self.plugin_list)
        
        controls_layout = QHBoxLayout()
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh_plugins)
        self.settings_button = QPushButton("Plugin Settings")
        self.settings_button.clicked.connect(self.show_plugin_settings)
        controls_layout.addWidget(self.refresh_button)
        controls_layout.addWidget(self.settings_button)
        layout.addLayout(controls_layout)
        
        self.info_label = QLabel()
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)
        
        self.setLayout(layout)
        self.refresh_plugins()
        
    def refresh_plugins(self):
        self.plugin_list.clear()
        for plugin_name, plugin in self.plugin_manager.plugins.items():
            item = QListWidgetItem()
            widget = QWidget()
            layout = QHBoxLayout()
            
            name_label = QLabel(f"{plugin.name} v{plugin.version}")
            layout.addWidget(name_label)
            
            checkbox = QCheckBox("Enabled")
            checkbox.setChecked(plugin.enabled)
            checkbox.stateChanged.connect(lambda state, p=plugin: self.toggle_plugin(p, state))
            layout.addWidget(checkbox)
            
            widget.setLayout(layout)
            item.setSizeHint(widget.sizeHint())
            self.plugin_list.addItem(item)
            self.plugin_list.setItemWidget(item, widget)
            
    def toggle_plugin(self, plugin, state):
        if state:
            self.plugin_manager.enable_plugin(plugin.name)
        else:
            self.plugin_manager.disable_plugin(plugin.name)
        self.refresh_plugins()
        
    def show_plugin_settings(self):
        dialog = PluginSettingsDialog(self.plugin_manager, self)
        if dialog.exec() == QDialog.Accepted:
            self.refresh_plugins()

class ClipboardManager(QMainWindow):
    def __init__(self, db_manager, fernet, settings, app_dir):
        super().__init__()
        self.settings = settings
        self.app_font = get_app_font(10, self.settings)
        self.setFont(self.app_font)
        self.db_manager = db_manager
        self.fernet = fernet
        self.app_dir = app_dir
        self._allow_exit = False
        self.sync_timer = QTimer()
        self.sync_timer.timeout.connect(self.auto_sync)
        self.setup_sync_timer()

        # try to sync from gdrive on startup
        if self.settings.get('gdrive_enabled', False):
            QTimer.singleShot(1000, self.sync_from_gdrive)  # delay sync to allow UI to load

        # init managers
        self.plugin_manager = PluginManager(app_dir)
        self.notification_manager = NotificationManager(app_dir)

        # setup tray icon first
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.style().standardIcon(QStyle.SP_ComputerIcon))
        self.tray_icon.show()
        
        self.notification_manager.set_tray_icon(self.tray_icon)

        self.tab_widget = QTabWidget()
        self.all_list = QListWidget()
        self.fav_list = QListWidget()
        self.tab_widget.addTab(self.all_list, "all")
        self.tab_widget.addTab(self.fav_list, "favorites")
        
        self.plugin_tab = PluginTab(self.plugin_manager, self)
        self.tab_widget.addTab(self.plugin_tab, "plugins")
        
        self.clipboard = QApplication.clipboard()
        self.clipboard.dataChanged.connect(self.on_clipboard_change)
        self.last_clipboard_text = ""

        self.initUI()
        
    def setup_sync_timer(self):
        if self.settings.get('gdrive_enabled', False):
            # sync every 5 minutes if enabled
            self.sync_timer.start(5 * 60 * 1000)
        else:
            self.sync_timer.stop()

    def initUI(self):
        self.setWindowTitle("clipboard manager")
        self.setGeometry(100, 100, 600, 400)
        self.setFont(self.app_font)
        theme = self.settings.get("theme", "light")
        if "dark" in theme:
            self.setStyleSheet(RAVENS_WING_DARK_STYLE)
        elif "system" in theme:
            system_theme = get_system_theme()
            if system_theme == "dark":
                self.setStyleSheet(RAVENS_WING_DARK_STYLE)
            else:
                self.setStyleSheet("")
        else:
            self.setStyleSheet("")

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout()

        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("search clipboard history... (filters: date:yyyy-mm-dd, type:code/text)")
        self.search_bar.textChanged.connect(self.on_search)
        layout.addWidget(self.search_bar)

        sync_layout = QHBoxLayout()
        self.sync_button = QPushButton("sync with Google Drive")
        self.sync_button.clicked.connect(self.sync_with_gdrive)
        sync_layout.addWidget(self.sync_button)
        layout.addLayout(sync_layout)

        layout.addWidget(self.tab_widget)

        self.detail_view = QPlainTextEdit()
        self.detail_view.setReadOnly(True)
        layout.addWidget(self.detail_view)

        self.copy_button = QPushButton("copy to clipboard")
        self.copy_button.clicked.connect(self.copy_selected)
        layout.addWidget(self.copy_button)

        central_widget.setLayout(layout)
        self.load_history()

        script_dir = os.path.dirname(os.path.realpath(__file__))
        if getattr(sys, 'frozen', False):
            clipboard_icon_path = os.path.join(sys._MEIPASS, "clipboard.png")
        else:
            clipboard_icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "clipboard.png")
        if os.path.exists(clipboard_icon_path):
            icon = QIcon(clipboard_icon_path)
        else:
            icon = self.style().standardIcon(QStyle.SP_FileIcon)
            print("clipboard.png not found, falling back to default icon")
        
        self.tray_icon.setIcon(icon)

        tray_menu = QMenu()
        restore_action = QAction("restore", self)
        restore_action.triggered.connect(self.show)
        tray_menu.addAction(restore_action)

        settings_action = QAction("settings", self)
        settings_action.triggered.connect(self.open_settings)
        tray_menu.addAction(settings_action)

        exit_action = QAction("exit", self)
        exit_action.triggered.connect(self.exit_app)
        tray_menu.addAction(exit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_icon_activated)
        self.tray_icon.show()

    def closeEvent(self, event):
        if self._allow_exit:
            event.accept()
        else:
            event.ignore()
            self.hide()

    def exit_app(self):
        self._allow_exit = True
        self.close()
        QApplication.quit()

    def on_tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.showNormal()
            self.activateWindow()

    def on_clipboard_change(self, *args):
        # the clipboard.dataChanged signal doesn't provide text directly so get from clipboard
        text = self.clipboard.text()
        if text and text != self.last_clipboard_text:
            self.last_clipboard_text = text
            
            # process text through plugins due to conflicts
            transformed_text = text
            for plugin in self.plugin_manager.get_enabled_plugins():
                if plugin.instance and hasattr(plugin.instance, 'on_clipboard_change'):
                    result = plugin.instance.on_clipboard_change(transformed_text)
                    if result:
                        transformed_text = result
            
            # save the transformed text to history
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            code_flag = is_code(transformed_text)
            encrypted_text = encrypt_text(transformed_text, self.fernet)
            self.db_manager.add_entry(encrypted_text, timestamp, code_flag)
            self.load_history()
            
            # check for notifications
            self.notification_manager.check_text(transformed_text)
            
            # update clipboard with transformed text if it changed
            if transformed_text != text:
                self.clipboard.setText(transformed_text)
                self.last_clipboard_text = transformed_text

    def load_history(self):
        self.all_list.clear()
        self.fav_list.clear()
        entries = self.db_manager.get_all_entries()
        for entry in entries:
            # entry: (id, text, timestamp, is_code, pinned, favorite)
            decrypted_text = decrypt_text(entry[1], self.fernet)
            preview = decrypted_text if len(decrypted_text) <= 50 else decrypted_text[:50] + "..."
            item_widget = HistoryItemWidget(entry[0], preview, entry[2], entry[3], entry[4], entry[5])
            item_widget.clicked.connect(self.load_detail)
            item_widget.trash_button.clicked.connect(lambda checked, eid=entry[0]: self.delete_entry(eid))
            item_widget.star_button.clicked.connect(lambda checked, eid=entry[0]: self.favorite_entry(eid))
            item_widget.pin_button.clicked.connect(lambda checked, eid=entry[0]: self.pin_entry(eid))
            list_item = QListWidgetItem()
            list_item.setSizeHint(item_widget.sizeHint())
            self.all_list.addItem(list_item)
            self.all_list.setItemWidget(list_item, item_widget)
            if entry[5]:
                fav_item = QListWidgetItem()
                fav_item.setSizeHint(item_widget.sizeHint())
                fav_widget = HistoryItemWidget(entry[0], preview, entry[2], entry[3], entry[4], entry[5])
                fav_widget.clicked.connect(self.load_detail)
                fav_widget.trash_button.clicked.connect(lambda checked, eid=entry[0]: self.delete_entry(eid))
                fav_widget.star_button.clicked.connect(lambda checked, eid=entry[0]: self.favorite_entry(eid))
                fav_widget.pin_button.clicked.connect(lambda checked, eid=entry[0]: self.pin_entry(eid))
                self.fav_list.addItem(fav_item)
                self.fav_list.setItemWidget(fav_item, fav_widget)

    def load_detail(self, entry_id):
        row = self.db_manager.get_entry_by_id(entry_id)
        if row:
            decrypted_text = decrypt_text(row[0], self.fernet)
            self.detail_view.setPlainText(decrypted_text)

    def delete_entry(self, entry_id):
        self.db_manager.delete_entry_by_id(entry_id)
        self.load_history()

    def favorite_entry(self, entry_id):
        # toggle favorite state
        row = self.db_manager.get_entry_by_id(entry_id)
        if row:
            current_state = row[2] if len(row) >= 3 else 0  # row: (text, pinned, favorite)
            entries = self.db_manager.get_all_entries()
            fav_state = 0
            for e in entries:
                if e[0] == entry_id:
                    fav_state = e[5]
                    break
            new_state = 0 if fav_state else 1
            self.db_manager.update_favorite_state(entry_id, new_state)
            self.load_history()

    def pin_entry(self, entry_id):
        # toggle pinned state
        entries = self.db_manager.get_all_entries()
        pin_state = 0
        for e in entries:
            if e[0] == entry_id:
                pin_state = e[4]
                break
        new_state = 0 if pin_state else 1
        self.db_manager.update_pin_state(entry_id, new_state)
        self.load_history()

    def on_search(self, search_term):
        self.all_list.clear()
        self.fav_list.clear()
        entries = self.db_manager.get_all_entries()
        date_filter = None
        type_filter = None
        date_match = re.search(r"date:\s*(\d{4}-\d{2}-\d{2})", search_term, re.IGNORECASE)
        if date_match:
            date_filter = date_match.group(1)
            search_term = re.sub(r"date:\s*\d{4}-\d{2}-\d{2}", "", search_term, flags=re.IGNORECASE)
        type_match = re.search(r"type:\s*(code|text)", search_term, re.IGNORECASE)
        if type_match:
            type_filter = type_match.group(1).lower()
            search_term = re.sub(r"type:\s*(code|text)", "", search_term, flags=re.IGNORECASE)
        search_term = search_term.strip().lower()
        for entry in entries:
            if date_filter and not entry[2].startswith(date_filter):
                continue
            if type_filter:
                if type_filter == "code" and not entry[3]:
                    continue
                elif type_filter == "text" and entry[3]:
                    continue
            decrypted_text = decrypt_text(entry[1], self.fernet)
            if search_term and search_term not in decrypted_text.lower():
                continue
            preview = decrypted_text if len(decrypted_text) <= 50 else decrypted_text[:50] + "..."
            item_widget = HistoryItemWidget(entry[0], preview, entry[2], entry[3], entry[4], entry[5])
            item_widget.clicked.connect(self.load_detail)
            item_widget.trash_button.clicked.connect(lambda checked, eid=entry[0]: self.delete_entry(eid))
            item_widget.star_button.clicked.connect(lambda checked, eid=entry[0]: self.favorite_entry(eid))
            item_widget.pin_button.clicked.connect(lambda checked, eid=entry[0]: self.pin_entry(eid))
            list_item = QListWidgetItem()
            list_item.setSizeHint(item_widget.sizeHint())
            self.all_list.addItem(list_item)
            self.all_list.setItemWidget(list_item, item_widget)
            if entry[5]:
                fav_item = QListWidgetItem()
                fav_item.setSizeHint(item_widget.sizeHint())
                fav_widget = HistoryItemWidget(entry[0], preview, entry[2], entry[3], entry[4], entry[5])
                fav_widget.clicked.connect(self.load_detail)
                fav_widget.trash_button.clicked.connect(lambda checked, eid=entry[0]: self.delete_entry(eid))
                fav_widget.star_button.clicked.connect(lambda checked, eid=entry[0]: self.favorite_entry(eid))
                fav_widget.pin_button.clicked.connect(lambda checked, eid=entry[0]: self.pin_entry(eid))
                self.fav_list.addItem(fav_item)
                self.fav_list.setItemWidget(fav_item, fav_widget)

    def copy_selected(self):
        clipboard_text = self.detail_view.toPlainText()
        if clipboard_text:
            self.clipboard.setText(clipboard_text)

    def apply_theme(self, theme):
        """Apply the selected theme to the main window."""
        if "dark" in theme:
            self.setStyleSheet(RAVENS_WING_DARK_STYLE)
        elif "system" in theme:
            system_theme = get_system_theme()
            if system_theme == "dark":
                self.setStyleSheet(RAVENS_WING_DARK_STYLE)
            else:
                self.setStyleSheet("")
        else:
            self.setStyleSheet("")

    def open_settings(self):
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec() == QDialog.Accepted:
            self.settings = dialog.current_settings
            
            theme = self.settings.get("theme", "system")
            self.apply_theme(theme)
            
            self.setup_sync_timer()
            
            self.app_font = get_app_font(10, self.settings)
            self.setFont(self.app_font)
            for widget in self.findChildren(QWidget):
                widget.setFont(self.app_font)
                
            settings_path = os.path.join(self.app_dir, "settings.json")
            SettingsManager.save_settings(self.settings, settings_path)
            
            self.load_history()

    def sync_from_gdrive(self):
        if not self.settings.get('gdrive_enabled', False):
            return

        token_path = self.settings.get('gdrive_token', "")
        if not token_path:
            return

        try:
            # download from gdrive
            service = authenticate_gdrive(token_path)
            folder_id = get_or_create_app_folder(service)
            
            # create temp file for download
            temp_file = os.path.join(self.app_dir, 'temp_sync.json')
            if download_file(temp_file, service, folder_id):
                # load and merge data
                with open(temp_file, 'r') as f:
                    sync_data = json.load(f)

                # get existing entries
                existing_entries = {entry[2]: entry for entry in self.db_manager.get_all_entries()}

                # merge new entries
                for entry in sync_data:
                    timestamp = entry['timestamp']
                    if timestamp not in existing_entries:
                        # if new entry, we add it
                        self.db_manager.add_entry(
                            entry['text'].encode() if isinstance(entry['text'], str) else entry['text'],
                            timestamp,
                            entry['is_code']
                        )
                    else:
                        # update existing entry if needed
                        existing = existing_entries[timestamp]
                        if entry['pinned'] != existing[4] or entry['favorite'] != existing[5]:
                            if entry['pinned'] != existing[4]:
                                self.db_manager.update_pin_state(existing[0], entry['pinned'])
                            if entry['favorite'] != existing[5]:
                                self.db_manager.update_favorite_state(existing[0], entry['favorite'])

                # clean up
                os.remove(temp_file)
                self.load_history()  # refresh ui
        except Exception as e:
            QMessageBox.warning(self, "Google Drive Sync", f"Failed to sync from Google Drive: {e}")

    def sync_with_gdrive(self):
        if not self.settings.get('gdrive_enabled', False):
            QMessageBox.warning(self, "Google Drive Sync", "Google Drive sync is not enabled. Please enable it in settings.")
            return

        token_path = self.settings.get('gdrive_token', "")
        if not token_path:
            QMessageBox.warning(self, "Google Drive Sync", "No Google Drive token found. Please authenticate in settings.")
            return

        try:
            # first download any changes
            self.sync_from_gdrive()

            # then upload current state
            entries = self.db_manager.get_all_entries()
            sync_data = []
            for entry in entries:
                entry_id, enc_text, timestamp, is_code, pinned, favorite = entry
                sync_data.append({
                    'text': enc_text.decode() if isinstance(enc_text, bytes) else enc_text,
                    'timestamp': timestamp,
                    'is_code': is_code,
                    'pinned': pinned,
                    'favorite': favorite
                })

            temp_file = os.path.join(self.app_dir, 'temp_sync.json')
            with open(temp_file, 'w') as f:
                json.dump(sync_data, f)

            service = authenticate_gdrive(token_path)
            folder_id = get_or_create_app_folder(service)
            upload_file(temp_file, service, folder_id)

            os.remove(temp_file)
            QMessageBox.information(self, "Google Drive Sync", "Successfully synced with Google Drive!")
        except Exception as e:
            QMessageBox.critical(self, "Google Drive Sync", f"Failed to sync with Google Drive: {e}")

    def auto_sync(self):
        if self.settings.get('gdrive_enabled', False):
            self.sync_with_gdrive()

    def copy_to_clipboard(self):
        clipboard_text = self.detail_view.toPlainText()
        if clipboard_text:
            self.clipboard.setText(clipboard_text)

    def show_plugin_settings(self):
        dialog = PluginSettingsDialog(self.plugin_manager, self)
        dialog.exec() 