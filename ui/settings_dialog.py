from PySide6.QtWidgets import QDialog, QVBoxLayout, QCheckBox, QLabel, QLineEdit, QComboBox, QPushButton, QHBoxLayout, QFileDialog, QWidget, QMessageBox
from utils import get_app_font, get_system_theme, RAVENS_WING_DARK_STYLE
from ui.startup_wizard import add_to_startup, remove_from_startup
import os
from gdrive_sync import authenticate_gdrive, get_or_create_app_folder, upload_file, download_file, delete_file, unlink_gdrive_token

class SettingsDialog(QDialog):
    def __init__(self, current_settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("settings")
        self.current_settings = current_settings.copy()
        self.app_font = get_app_font(10, self.current_settings)
        self.setFont(self.app_font)
        self.setupUI()

    def setupUI(self):
        layout = QVBoxLayout()

        self.encryption_checkbox = QCheckBox("enable encryption")
        self.encryption_checkbox.setChecked(self.current_settings.get("encryption_enabled", True))
        layout.addWidget(self.encryption_checkbox)

        self.personal_key_checkbox = QCheckBox("use personal key/password")
        self.personal_key_checkbox.setChecked(self.current_settings.get("use_personal_key", False))
        layout.addWidget(self.personal_key_checkbox)

        self.password_label = QLabel("enter password:")
        self.password_field = QLineEdit()
        self.password_field.setEchoMode(QLineEdit.Password)
        self.password_field.setText(self.current_settings.get("personal_key", ""))
        self.password_field.setEnabled(self.personal_key_checkbox.isChecked())
        layout.addWidget(self.password_label)
        layout.addWidget(self.password_field)

        self.personal_key_checkbox.stateChanged.connect(
            lambda: self.password_field.setEnabled(self.personal_key_checkbox.isChecked())
        )

        theme_label = QLabel("select theme:")
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["system (default)", "light", "dark"])
        self.theme_combo.setCurrentIndex(0)
        current_theme = self.current_settings.get("theme", "system")
        if current_theme == "light":
            self.theme_combo.setCurrentIndex(1)
        elif current_theme == "dark":
            self.theme_combo.setCurrentIndex(2)
        layout.addWidget(theme_label)
        layout.addWidget(self.theme_combo)

        font_label = QLabel("custom font (optional):")
        self.font_path_field = QLineEdit()
        self.font_path_field.setText(self.current_settings.get("custom_font_path", ""))
        self.font_browse_button = QPushButton("browse")
        self.font_browse_button.clicked.connect(self.browse_font)
        font_layout = QHBoxLayout()
        font_layout.addWidget(self.font_path_field)
        font_layout.addWidget(self.font_browse_button)
        layout.addWidget(font_label)
        layout.addLayout(font_layout)

        self.timestamps_checkbox = QCheckBox("show timestamps in history")
        self.timestamps_checkbox.setChecked(self.current_settings.get("show_timestamps", True))
        layout.addWidget(self.timestamps_checkbox)

        self.startup_checkbox = QCheckBox("start at startup")
        self.startup_checkbox.setChecked(self.current_settings.get("start_at_startup", False))
        layout.addWidget(self.startup_checkbox)

        history_mgmt_label = QLabel("history management:")
        self.history_mgmt_combo = QComboBox()
        self.history_mgmt_combo.addItems(["keep all", "auto-delete", "archive"])
        current_history = self.current_settings.get("history_management", "keep").lower()
        if current_history == "keep":
            self.history_mgmt_combo.setCurrentIndex(0)
        elif current_history == "auto-delete":
            self.history_mgmt_combo.setCurrentIndex(1)
        elif current_history == "archive":
            self.history_mgmt_combo.setCurrentIndex(2)
        layout.addWidget(history_mgmt_label)
        layout.addWidget(self.history_mgmt_combo)

        threshold_label = QLabel("threshold (days):")
        self.threshold_field = QLineEdit(self.current_settings.get("history_threshold_days", "30"))
        layout.addWidget(threshold_label)
        layout.addWidget(self.threshold_field)

        # --- google Drive Sync Section ---
        self.gdrive_checkbox = QCheckBox("Enable Google Drive Sync")
        self.gdrive_checkbox.setChecked(self.current_settings.get('gdrive_enabled', False))
        layout.addWidget(self.gdrive_checkbox)

        self.gdrive_auth_button = QPushButton("Authenticate with Google Drive")
        self.gdrive_auth_button.clicked.connect(self.authenticate_gdrive)
        layout.addWidget(self.gdrive_auth_button)

        self.gdrive_status_label = QLabel()
        layout.addWidget(self.gdrive_status_label)

        self.gdrive_unlink_button = QPushButton("Unlink Google Drive Account")
        self.gdrive_unlink_button.clicked.connect(self.unlink_gdrive)
        layout.addWidget(self.gdrive_unlink_button)

        self.gdrive_delete_button = QPushButton("Delete Cloud Data from Google Drive")
        self.gdrive_delete_button.clicked.connect(self.delete_gdrive_data)
        layout.addWidget(self.gdrive_delete_button)

        self.save_button = QPushButton("save settings")
        self.save_button.clicked.connect(self.save_settings)
        layout.addWidget(self.save_button)

        self.setLayout(layout)
        self.update_gdrive_status()

    def browse_font(self):
        font_file, _ = QFileDialog.getOpenFileName(self, "select font file", "", "font files (*.ttf *.otf)")
        if font_file:
            self.font_path_field.setText(font_file)
            new_font = get_app_font(10, {"custom_font_path": font_file})
            self.app_font = new_font
            self.setFont(new_font)
            for widget in self.findChildren(QWidget):
                widget.setFont(new_font)

    def update_gdrive_status(self):
        if self.current_settings.get('gdrive_enabled', False):
            self.gdrive_status_label.setText("Google Drive Sync: ENABLED")
        else:
            self.gdrive_status_label.setText("Google Drive Sync: DISABLED")

    def authenticate_gdrive(self):
        # will start the oauth flow and store the token
        token_path = os.path.join(os.path.expanduser("~"), ".clipboardmanager_gdrive_token.pickle")
        credentials_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "credentials.json")
        
        try:
            service = authenticate_gdrive(token_path, credentials_path)
            folder_id = get_or_create_app_folder(service)
            self.current_settings['gdrive_enabled'] = True
            self.current_settings['gdrive_token'] = token_path
            QMessageBox.information(self, "Google Drive", "Authentication successful!")
        except FileNotFoundError as e:
            QMessageBox.critical(self, "Google Drive Authentication Failed", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Google Drive Authentication Failed", 
                f"Authentication failed: {str(e)}\n\n"
                "Please make sure you have:\n"
                "1. Created a Google Cloud Project\n"
                "2. Enabled the Google Drive API\n"
                "3. Created OAuth credentials for a Desktop app\n"
                "4. Downloaded and placed the credentials.json file in the app directory")
        self.update_gdrive_status()

    def unlink_gdrive(self):
        token_path = self.current_settings.get('gdrive_token', "")
        if token_path:
            unlink_gdrive_token(token_path)
        self.current_settings['gdrive_enabled'] = False
        self.current_settings['gdrive_token'] = ""
        QMessageBox.information(self, "Google Drive", "Google Drive account unlinked.")
        self.update_gdrive_status()

    def delete_gdrive_data(self):
        token_path = self.current_settings.get('gdrive_token', "")
        if not token_path:
            QMessageBox.warning(self, "Google Drive", "No Google Drive account linked.")
            return
        try:
            service = authenticate_gdrive(token_path)
            folder_id = get_or_create_app_folder(service)
            if delete_file(service, folder_id):
                QMessageBox.information(self, "Google Drive", "Cloud data deleted from Google Drive.")
            else:
                QMessageBox.warning(self, "Google Drive", "No cloud data found to delete.")
        except Exception as e:
            QMessageBox.critical(self, "Google Drive", f"Failed to delete cloud data: {e}")

    def save_settings(self):
        encryption_enabled = self.encryption_checkbox.isChecked()
        use_personal_key = self.personal_key_checkbox.isChecked()
        password = self.password_field.text().strip() if use_personal_key else ""
        theme = self.theme_combo.currentText().lower()
        if "system" in theme:
            theme = "system"
        show_timestamps = self.timestamps_checkbox.isChecked()
        start_at_startup = self.startup_checkbox.isChecked()
        custom_font_path = self.font_path_field.text().strip()
        history_management = self.history_mgmt_combo.currentText().lower()
        if history_management == "keep all":
            history_management = "keep"
        history_threshold_days = self.threshold_field.text().strip()
        gdrive_enabled = self.gdrive_checkbox.isChecked()
        
        # update settings
        self.current_settings.update({
            "encryption_enabled": encryption_enabled,
            "use_personal_key": use_personal_key,
            "personal_key": password,
            "theme": theme,
            "show_timestamps": show_timestamps,
            "start_at_startup": start_at_startup,
            "custom_font_path": custom_font_path,
            "history_management": history_management,
            "history_threshold_days": history_threshold_days,
            "gdrive_enabled": gdrive_enabled
        })
        
        # apply theme immediately
        self.apply_theme(theme)
        
        if start_at_startup:
            add_to_startup()
        else:
            remove_from_startup()
        self.accept()
        
    def apply_theme(self, theme):
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