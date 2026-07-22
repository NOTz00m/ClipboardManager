# settings sub-interface

from PySide6.QtWidgets import (QFrame, QVBoxLayout, QHBoxLayout, QWidget,
                                QScrollArea, QLabel, QFileDialog,
                                QListWidget, QListWidgetItem)
from PySide6.QtCore import Qt, Signal
from qfluentwidgets import (SwitchButton, ComboBox, LineEdit, PushButton,
                             PrimaryPushButton, CardWidget, isDarkTheme,
                             setTheme, Theme, BodyLabel, SubtitleLabel,
                             StrongBodyLabel, CaptionLabel, InfoBar,
                             MessageBox, PasswordLineEdit)

from utils import get_app_font, get_system_theme
from settings import DEFAULT_SETTINGS, SettingsManager
from ui.startup_wizard import add_to_startup, remove_from_startup
import os


class SettingsGroup(CardWidget):
    # section card with title and grouped controls

    def __init__(self, title, parent=None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(20, 16, 20, 16)
        self._layout.setSpacing(12)

        title_label = StrongBodyLabel(title)
        title_font = title_label.font()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title_label.setFont(title_font)
        self._layout.addWidget(title_label)

    def addRow(self, label_text, widget):
        row = QHBoxLayout()
        row.setSpacing(12)
        label = BodyLabel(label_text)
        label.setMinimumWidth(200)
        row.addWidget(label)
        row.addWidget(widget, 1)
        self._layout.addLayout(row)
        return row

    def addWidget(self, widget):
        self._layout.addWidget(widget)

    def addFullRow(self, widget):
        self._layout.addWidget(widget)


class SettingsPage(QFrame):
    # main settings page

    settingsChanged = Signal(dict)
    themeChanged = Signal(str)
    syncRequested = Signal()
    resetRequested = Signal()
    factoryResetRequested = Signal()

    def __init__(self, settings, app_dir, plugin_manager=None,
                 settings_encryption_key=None, parent=None):
        super().__init__(parent)
        self.settings = settings.copy()
        self.app_dir = app_dir
        self.plugin_manager = plugin_manager
        self.settings_encryption_key = settings_encryption_key
        self.setObjectName("settingsPage")
        self._setup_ui()

    def _setup_ui(self):
        # Main scroll area
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(24, 16, 24, 24)
        layout.setSpacing(16)

        # ── Appearance Section ────────────────────────────────────────
        appearance_group = SettingsGroup("Appearance")

        # Theme
        self.theme_combo = ComboBox()
        self.theme_combo.addItems(["System (Default)", "Light", "Dark"])
        current_theme = self.settings.get("theme", "system")
        if current_theme == "light":
            self.theme_combo.setCurrentIndex(1)
        elif current_theme == "dark":
            self.theme_combo.setCurrentIndex(2)
        else:
            self.theme_combo.setCurrentIndex(0)
        self.theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        appearance_group.addRow("Theme", self.theme_combo)

        # Custom font
        font_row = QWidget()
        font_layout = QHBoxLayout(font_row)
        font_layout.setContentsMargins(0, 0, 0, 0)
        self.font_path_field = LineEdit()
        self.font_path_field.setText(self.settings.get("custom_font_path", ""))
        self.font_path_field.setPlaceholderText("Default (JetBrains Mono)")
        font_layout.addWidget(self.font_path_field, 1)
        self.font_browse_btn = PushButton("Browse")
        self.font_browse_btn.clicked.connect(self._browse_font)
        font_layout.addWidget(self.font_browse_btn)
        appearance_group.addRow("Custom Font", font_row)

        # Show timestamps
        self.timestamps_switch = SwitchButton()
        self.timestamps_switch.setChecked(self.settings.get("show_timestamps", True))
        appearance_group.addRow("Show Timestamps", self.timestamps_switch)

        layout.addWidget(appearance_group)

        # ── Security & Encryption Section ─────────────────────────────
        security_group = SettingsGroup("Security & Encryption")

        # Encryption enabled
        self.encryption_switch = SwitchButton()
        self.encryption_switch.setChecked(self.settings.get("encryption_enabled", True))
        self.encryption_switch.checkedChanged.connect(self._on_encryption_toggled)
        self.encryption_switch.setEnabled(False)
        security_group.addRow("Protect clipboard data (Encryption)", self.encryption_switch)

        # Encryption status indicator
        enc_enabled = self.settings.get("encryption_enabled", True)
        status_text = "🔒 Active — Your clipboard data is protected and encrypted on your device" if enc_enabled else "🔓 Disabled — Data stored in plaintext"
        self.encryption_status = CaptionLabel(status_text)
        if enc_enabled:
            self.encryption_status.setStyleSheet("color: #10B981;")
        else:
            self.encryption_status.setStyleSheet("color: #EF4444;")
        security_group.addFullRow(self.encryption_status)

        # Personal key
        self.personal_key_switch = SwitchButton()
        self.personal_key_switch.setChecked(self.settings.get("use_personal_key", False))
        self.personal_key_switch.checkedChanged.connect(self._on_personal_key_toggled)
        self.personal_key_switch.setEnabled(False)
        security_group.addRow("Use Personal Password", self.personal_key_switch)

        # Password field with proper echo mode
        self.password_field = PasswordLineEdit()
        self.password_field.setText(self.settings.get("personal_key", ""))
        self.password_field.setPlaceholderText("Enter encryption password...")
        self.password_field.setEnabled(False)
        security_group.addRow("Password", self.password_field)

        # Password strength hint
        self.password_hint = CaptionLabel("Use 12+ characters with mixed case, numbers, and symbols")
        self.password_hint.setStyleSheet("color: #6B7280;")
        self.password_hint.setVisible(self.personal_key_switch.isChecked())
        security_group.addFullRow(self.password_hint)

        security_note = CaptionLabel(
            "Encryption is fixed for this data store to prevent unreadable history. "
            "Use Factory Reset if you need to choose a different mode."
        )
        security_note.setWordWrap(True)
        security_note.setStyleSheet("color: #6B7280;")
        security_group.addFullRow(security_note)

        layout.addWidget(security_group)

        # ── History Management Section ────────────────────────────────
        history_group = SettingsGroup("History Management")

        self.history_combo = ComboBox()
        self.history_combo.addItems(["Keep All", "Auto-Delete", "Archive"])
        current_history = self.settings.get("history_management", "keep").lower()
        if current_history == "auto-delete":
            self.history_combo.setCurrentIndex(1)
        elif current_history == "archive":
            self.history_combo.setCurrentIndex(2)
        else:
            self.history_combo.setCurrentIndex(0)
        self.history_combo.currentIndexChanged.connect(self._on_history_mode_changed)
        history_group.addRow("History Mode", self.history_combo)

        # Threshold row — hidden when "Keep All"
        self.threshold_field = LineEdit()
        self.threshold_field.setText(self.settings.get("history_threshold_days", "30"))
        self.threshold_field.setPlaceholderText("30")

        self.threshold_label = BodyLabel("Threshold (days)")
        self.threshold_label.setMinimumWidth(200)

        self.threshold_row = QWidget()
        threshold_layout = QHBoxLayout(self.threshold_row)
        threshold_layout.setSpacing(12)
        threshold_layout.setContentsMargins(0, 0, 0, 0)
        threshold_layout.addWidget(self.threshold_label)
        threshold_layout.addWidget(self.threshold_field, 1)
        history_group.addFullRow(self.threshold_row)

        # Set initial visibility
        self.threshold_row.setVisible(self.history_combo.currentIndex() != 0)

        layout.addWidget(history_group)

        # ── Shortcuts Section ─────────────────────────────────────────
        shortcuts_group = SettingsGroup("Keyboard Shortcuts")

        self.shortcut_field = LineEdit()
        self.shortcut_field.setText(self.settings.get("global_shortcut", "ctrl+alt+v"))
        self.shortcut_field.setPlaceholderText("e.g. ctrl+alt+v")
        shortcuts_group.addRow("Show Window", self.shortcut_field)

        shortcut_desc = CaptionLabel("Global hotkey to bring the clipboard manager to the front.")
        shortcut_desc.setStyleSheet("color: #6B7280;")
        shortcuts_group.addFullRow(shortcut_desc)

        layout.addWidget(shortcuts_group)

        # ── System Section ────────────────────────────────────────────
        startup_group = SettingsGroup("System")

        self.startup_switch = SwitchButton()
        self.startup_switch.setChecked(self.settings.get("start_at_startup", False))
        startup_group.addRow("Start at Startup", self.startup_switch)

        layout.addWidget(startup_group)

        # ── Google Drive Sync Section ─────────────────────────────────
        gdrive_group = SettingsGroup("Google Drive Sync")

        self.gdrive_switch = SwitchButton()
        self.gdrive_switch.setChecked(self.settings.get("gdrive_enabled", False))
        gdrive_group.addRow("Enable Sync", self.gdrive_switch)

        self.gdrive_status = CaptionLabel(
            "🟢 ENABLED" if self.settings.get("gdrive_enabled", False) else "⚫ DISABLED"
        )
        gdrive_group.addRow("Status", self.gdrive_status)

        gdrive_desc = CaptionLabel("For maximum security and privacy, you must provide your own Google API credentials. This ensures your data is only accessible to you.")
        gdrive_desc.setWordWrap(True)
        gdrive_desc.setStyleSheet("color: #6B7280;")
        gdrive_group.addFullRow(gdrive_desc)

        gdrive_buttons = QWidget()
        gdrive_btn_layout = QHBoxLayout(gdrive_buttons)
        gdrive_btn_layout.setContentsMargins(0, 0, 0, 0)
        gdrive_btn_layout.setSpacing(8)

        self.gdrive_auth_btn = PrimaryPushButton("Authenticate")
        self.gdrive_auth_btn.clicked.connect(self._authenticate_gdrive)
        gdrive_btn_layout.addWidget(self.gdrive_auth_btn)

        self.gdrive_sync_btn = PushButton("Sync Now")
        self.gdrive_sync_btn.clicked.connect(lambda: self.syncRequested.emit())
        gdrive_btn_layout.addWidget(self.gdrive_sync_btn)

        self.gdrive_unlink_btn = PushButton("Unlink Account")
        self.gdrive_unlink_btn.clicked.connect(self._unlink_gdrive)
        gdrive_btn_layout.addWidget(self.gdrive_unlink_btn)

        self.gdrive_delete_btn = PushButton("Delete Cloud Data")
        self.gdrive_delete_btn.clicked.connect(self._delete_gdrive_data)
        gdrive_btn_layout.addWidget(self.gdrive_delete_btn)

        gdrive_group.addFullRow(gdrive_buttons)
        layout.addWidget(gdrive_group)

        # ── Plugins Section ───────────────────────────────────────────
        if self.plugin_manager:
            plugins_group = SettingsGroup("Plugins")

            self.plugin_list = QListWidget()
            self.plugin_list.setMaximumHeight(150)
            self._refresh_plugins()
            plugins_group.addFullRow(self.plugin_list)

            plugin_buttons = QWidget()
            plugin_btn_layout = QHBoxLayout(plugin_buttons)
            plugin_btn_layout.setContentsMargins(0, 0, 0, 0)

            refresh_btn = PushButton("Refresh Plugins")
            refresh_btn.clicked.connect(self._refresh_plugins)
            plugin_btn_layout.addWidget(refresh_btn)

            plugin_settings_btn = PushButton("Plugin Settings")
            plugin_settings_btn.clicked.connect(self._show_plugin_settings)
            plugin_btn_layout.addWidget(plugin_settings_btn)
            plugin_btn_layout.addStretch()

            plugins_group.addFullRow(plugin_buttons)
            layout.addWidget(plugins_group)

        # ── Danger Zone ───────────────────────────────────────────────
        danger_group = SettingsGroup("Danger Zone")

        reset_history_btn = PushButton("Clear All History")
        reset_history_btn.setStyleSheet("PushButton { color: #EF4444; }")
        reset_history_btn.clicked.connect(self._reset_history)

        reset_settings_btn = PushButton("Reset All Settings")
        reset_settings_btn.setStyleSheet("PushButton { color: #EF4444; }")
        reset_settings_btn.clicked.connect(self._reset_settings)

        reset_all_btn = PushButton("Factory Reset (Everything)")
        reset_all_btn.setStyleSheet("PushButton { color: #EF4444; }")
        reset_all_btn.clicked.connect(self._factory_reset)

        danger_buttons = QWidget()
        danger_layout = QHBoxLayout(danger_buttons)
        danger_layout.setContentsMargins(0, 0, 0, 0)
        danger_layout.setSpacing(8)
        danger_layout.addWidget(reset_history_btn)
        danger_layout.addWidget(reset_settings_btn)
        danger_layout.addWidget(reset_all_btn)
        danger_layout.addStretch()
        danger_group.addFullRow(danger_buttons)

        layout.addWidget(danger_group)

        # ── Save Button ──────────────────────────────────────────────
        save_row = QHBoxLayout()
        save_row.addStretch()
        self.save_btn = PrimaryPushButton("Save Settings")
        self.save_btn.setMinimumWidth(160)
        self.save_btn.clicked.connect(self._save_settings)
        save_row.addWidget(self.save_btn)
        save_row.addStretch()
        layout.addLayout(save_row)

        layout.addStretch()

        scroll.setWidget(container)

        # Set scroll area as the page content
        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.addWidget(scroll)

    # ── Event handlers ────────────────────────────────────────────────

    def _on_theme_changed(self, index):
        theme_map = {0: "system", 1: "light", 2: "dark"}
        theme = theme_map.get(index, "system")
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
        self.themeChanged.emit(theme)

    def _on_encryption_toggled(self, checked):
        if checked:
            self.encryption_status.setText("🔒 Active — Your clipboard data is protected and encrypted on your device")
            self.encryption_status.setStyleSheet("color: #10B981;")
        else:
            self.encryption_status.setText("🔓 Disabled — Data stored in plaintext")
            self.encryption_status.setStyleSheet("color: #EF4444;")

    def _on_personal_key_toggled(self, checked):
        self.password_field.setEnabled(checked)
        self.password_hint.setVisible(checked)

    def _on_history_mode_changed(self, index):
        # Hide threshold when "Keep All" (index 0)
        self.threshold_row.setVisible(index != 0)

    def _browse_font(self):
        font_file, _ = QFileDialog.getOpenFileName(
            self, "Select Font File", "", "Font Files (*.ttf *.otf)"
        )
        if font_file:
            self.font_path_field.setText(font_file)

    # ── Google Drive ──────────────────────────────────────────────────

    def _authenticate_gdrive(self):
        from gdrive_sync import authenticate_gdrive, get_or_create_app_folder

        token_path = os.path.join(
            os.path.expanduser("~"), ".clipboardmanager_gdrive_token.pickle"
        )
        credentials_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "credentials.json"
        )
        try:
            service = authenticate_gdrive(token_path, credentials_path)
            get_or_create_app_folder(service)
            self.settings['gdrive_enabled'] = True
            self.settings['gdrive_token'] = token_path
            self.gdrive_switch.setChecked(True)
            self.gdrive_status.setText("🟢 ENABLED")
            InfoBar.success("Google Drive", "Authentication successful!", parent=self)
        except Exception as e:
            w = MessageBox("Google Drive Authentication Failed", str(e), self)
            w.exec()

    def _unlink_gdrive(self):
        from gdrive_sync import unlink_gdrive_token

        token_path = self.settings.get('gdrive_token', "")
        if token_path:
            unlink_gdrive_token(token_path)
        self.settings['gdrive_enabled'] = False
        self.settings['gdrive_token'] = ""
        self.gdrive_switch.setChecked(False)
        self.gdrive_status.setText("⚫ DISABLED")
        InfoBar.success("Google Drive", "Account unlinked.", parent=self)

    def _delete_gdrive_data(self):
        from gdrive_sync import authenticate_gdrive, delete_file, get_or_create_app_folder

        token_path = self.settings.get('gdrive_token', "")
        if not token_path:
            InfoBar.warning("Google Drive", "No account linked.", parent=self)
            return
        try:
            service = authenticate_gdrive(token_path)
            folder_id = get_or_create_app_folder(service)
            if delete_file(service, folder_id):
                InfoBar.success("Google Drive", "Cloud data deleted.", parent=self)
            else:
                InfoBar.warning("Google Drive", "No cloud data found.", parent=self)
        except Exception as e:
            InfoBar.error("Google Drive", f"Failed: {e}", parent=self)

    # ── Plugins ───────────────────────────────────────────────────────

    def _refresh_plugins(self):
        if not self.plugin_manager:
            return
        self.plugin_list.clear()
        for plugin_name, plugin in self.plugin_manager.plugins.items():
            status = "✓ Enabled" if plugin.enabled else "✗ Disabled"
            item = QListWidgetItem(f"{plugin.name} v{plugin.version}  [{status}]")
            self.plugin_list.addItem(item)

    def _show_plugin_settings(self):
        if self.plugin_manager:
            from ui.plugin_settings_dialog import PluginSettingsDialog
            dialog = PluginSettingsDialog(self.plugin_manager, self)
            dialog.exec()
            self._refresh_plugins()

    # ── Danger Zone ───────────────────────────────────────────────────

    def _reset_history(self):
        w = MessageBox(
            "Clear All History",
            "This will permanently delete all clipboard history entries. This cannot be undone.\n\nAre you sure?",
            self
        )
        if w.exec():
            self.resetRequested.emit()
            InfoBar.success("Reset", "All history cleared.", parent=self)

    def _reset_settings(self):
        w = MessageBox(
            "Reset All Settings",
            "This will reset all settings to their defaults. The app will need to restart.\n\nAre you sure?",
            self
        )
        if w.exec():
            settings_path = os.path.join(self.app_dir, "settings.json")
            reset_settings = DEFAULT_SETTINGS.copy()
            # The database is preserved by this action, so its encryption
            # configuration must be preserved too.
            for key in (
                "encryption_enabled",
                "use_personal_key",
                "personal_key",
                "encryption_salt",
                "encryption_mode",
            ):
                reset_settings[key] = self.settings.get(key, DEFAULT_SETTINGS[key])
            SettingsManager.save_settings(
                reset_settings, settings_path, self.settings_encryption_key
            )
            InfoBar.success(
                "Reset",
                "Settings reset safely. Encryption was preserved; restart the app to apply defaults.",
                parent=self,
            )

    def _factory_reset(self):
        w = MessageBox(
            "Factory Reset",
            "This will delete ALL data including:\n• Clipboard history\n• Snippets & tags\n• Settings\n• Encryption keys\n\nThis cannot be undone. Are you sure?",
            self
        )
        if w.exec():
            self.factoryResetRequested.emit()
            InfoBar.success("Reset", "Factory reset complete. Please restart the app.", parent=self)

    # ── Save ──────────────────────────────────────────────────────────

    def _save_settings(self):
        theme_text = self.theme_combo.currentText().lower()
        if "system" in theme_text:
            theme = "system"
        elif "light" in theme_text:
            theme = "light"
        else:
            theme = "dark"

        history_text = self.history_combo.currentText().lower()
        if history_text == "keep all":
            history_management = "keep"
        else:
            history_management = history_text

        self.settings.update({
            "encryption_enabled": self.encryption_switch.isChecked(),
            "use_personal_key": self.personal_key_switch.isChecked(),
            "personal_key": self.password_field.text().strip() if self.personal_key_switch.isChecked() else "",
            "theme": theme,
            "show_timestamps": self.timestamps_switch.isChecked(),
            "start_at_startup": self.startup_switch.isChecked(),
            "global_shortcut": self.shortcut_field.text().strip() or "ctrl+alt+v",
            "custom_font_path": self.font_path_field.text().strip(),
            "history_management": history_management,
            "history_threshold_days": self.threshold_field.text().strip(),
            "gdrive_enabled": self.gdrive_switch.isChecked(),
        })

        if self.startup_switch.isChecked():
            add_to_startup()
        else:
            remove_from_startup()

        # Save to disk
        settings_path = os.path.join(self.app_dir, "settings.json")
        SettingsManager.save_settings(
            self.settings, settings_path, self.settings_encryption_key
        )

        self.settingsChanged.emit(self.settings)

        InfoBar.success("Settings", "Settings saved successfully!", parent=self)
