from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QWidget,
                                QListWidget, QListWidgetItem)
from PySide6.QtCore import Qt
from qfluentwidgets import (PushButton, PrimaryPushButton, CardWidget,
                             BodyLabel, StrongBodyLabel, CaptionLabel,
                             SwitchButton)


class PluginSettingsDialog(QDialog):
    # plugin settings dialog

    def __init__(self, plugin_manager, parent=None):
        super().__init__(parent)
        self.plugin_manager = plugin_manager
        self.setWindowTitle("Plugin Settings")
        self.setMinimumSize(500, 420)
        self.resize(560, 480)
        self._setup_ui()
        self._load_plugins()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(16)

        header = StrongBodyLabel("Installed Plugins")
        header_font = header.font()
        header_font.setPointSize(14)
        header_font.setBold(True)
        header.setFont(header_font)
        layout.addWidget(header)

        desc = CaptionLabel("Manage your plugins. Click a plugin to see details.")
        desc.setStyleSheet("color: #6B7280;")
        layout.addWidget(desc)

        self.plugin_list = QListWidget()
        self.plugin_list.setMinimumHeight(120)
        self.plugin_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #3D3D3D;
                border-radius: 6px;
                padding: 4px;
            }
            QListWidget::item {
                padding: 8px 12px;
                border-radius: 4px;
            }
            QListWidget::item:selected {
                background-color: #0078D4;
                color: white;
            }
            QListWidget::item:hover {
                background-color: rgba(0, 120, 212, 0.1);
            }
        """)
        self.plugin_list.currentItemChanged.connect(self._on_plugin_selected)
        layout.addWidget(self.plugin_list)

        self.details_card = CardWidget()
        details_layout = QVBoxLayout(self.details_card)
        details_layout.setContentsMargins(16, 12, 16, 12)
        details_layout.setSpacing(6)

        self.name_label = StrongBodyLabel("Select a plugin")
        name_font = self.name_label.font()
        name_font.setPointSize(11)
        self.name_label.setFont(name_font)
        details_layout.addWidget(self.name_label)

        self.version_label = CaptionLabel("")
        self.version_label.setStyleSheet("color: #6B7280;")
        details_layout.addWidget(self.version_label)

        self.author_label = CaptionLabel("")
        self.author_label.setStyleSheet("color: #6B7280;")
        details_layout.addWidget(self.author_label)

        self.description_label = BodyLabel("")
        self.description_label.setWordWrap(True)
        details_layout.addWidget(self.description_label)

        enable_row = QHBoxLayout()
        enable_label = BodyLabel("Enabled")
        enable_row.addWidget(enable_label)
        self.enable_switch = SwitchButton()
        self.enable_switch.setEnabled(False)
        self.enable_switch.checkedChanged.connect(self._on_toggle_plugin)
        enable_row.addWidget(self.enable_switch)
        enable_row.addStretch()
        details_layout.addLayout(enable_row)

        layout.addWidget(self.details_card)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        refresh_btn = PushButton("Refresh")
        refresh_btn.clicked.connect(self._load_plugins)
        btn_layout.addWidget(refresh_btn)

        close_btn = PrimaryPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    def _load_plugins(self):
        self.plugin_list.clear()
        for plugin_name, plugin in self.plugin_manager.plugins.items():
            status = "✓" if plugin.enabled else "✗"
            item = QListWidgetItem(f"{status}  {plugin.name}  (v{plugin.version})")
            item.setData(Qt.UserRole, plugin_name)
            self.plugin_list.addItem(item)

    def _on_plugin_selected(self, current, previous):
        if not current:
            return
        plugin_name = current.data(Qt.UserRole)
        plugin = self.plugin_manager.plugins.get(plugin_name)
        if plugin:
            self.name_label.setText(plugin.name)
            self.version_label.setText(f"Version {plugin.version}")
            self.author_label.setText(f"by {plugin.author}")
            self.description_label.setText(plugin.description or "No description available.")
            self.enable_switch.setEnabled(True)
            self.enable_switch.setChecked(plugin.enabled)

    def _on_toggle_plugin(self, checked):
        current = self.plugin_list.currentItem()
        if current:
            plugin_name = current.data(Qt.UserRole)
            plugin = self.plugin_manager.plugins.get(plugin_name)
            if plugin:
                plugin.enabled = checked
                self._load_plugins()