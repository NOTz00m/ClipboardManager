from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QListWidget, QListWidgetItem, QWidget,
                             QCheckBox, QTextEdit)
from PySide6.QtCore import Qt

class PluginSettingsDialog(QDialog):
    def __init__(self, plugin_manager, parent=None):
        super().__init__(parent)
        self.plugin_manager = plugin_manager
        self.setWindowTitle("Plugin Settings")
        self.setup_ui()
        self.load_plugins()
        
    def setup_ui(self):
        layout = QVBoxLayout()
        
        self.plugin_list = QListWidget()
        self.plugin_list.currentItemChanged.connect(self.on_plugin_selected)
        layout.addWidget(QLabel("Installed Plugins:"))
        layout.addWidget(self.plugin_list)
        
        details_widget = QWidget()
        details_layout = QVBoxLayout()
        
        self.name_label = QLabel()
        self.version_label = QLabel()
        self.author_label = QLabel()
        self.description_label = QLabel()
        self.description_label.setWordWrap(True)
        
        details_layout.addWidget(self.name_label)
        details_layout.addWidget(self.version_label)
        details_layout.addWidget(self.author_label)
        details_layout.addWidget(QLabel("Description:"))
        details_layout.addWidget(self.description_label)
        
        details_widget.setLayout(details_layout)
        layout.addWidget(details_widget)
        
        button_layout = QHBoxLayout()
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.load_plugins)
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.accept)
        
        button_layout.addWidget(self.refresh_button)
        button_layout.addWidget(self.close_button)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
    def load_plugins(self):
        self.plugin_list.clear()
        for plugin in self.plugin_manager.plugins.values():
            item = QListWidgetItem(plugin.name)
            item.setData(Qt.UserRole, plugin)
            self.plugin_list.addItem(item)
            
    def on_plugin_selected(self, current, previous):
        if not current:
            return
            
        plugin = current.data(Qt.UserRole)
        self.name_label.setText(f"Name: {plugin.name}")
        self.version_label.setText(f"Version: {plugin.version}")
        self.author_label.setText(f"Author: {plugin.author}")
        self.description_label.setText(plugin.description) 