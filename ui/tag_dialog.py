from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QListWidget, QListWidgetItem, QVBoxLayout
from qfluentwidgets import LineEdit


class TagDialog(QDialog):
    # dialog for toggling or creating tags on items

    def __init__(self, db_manager, entry_id, entry_type="history", parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.entry_id = entry_id
        self.entry_type = entry_type
        self.setWindowTitle("Manage tags")
        self.setMinimumSize(380, 360)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        description = QLabel("Select any existing tags for this item.")
        layout.addWidget(description)

        current_ids = {
            tag_id
            for tag_id, _name, _color in db_manager.get_tags_for_entry(entry_id, entry_type)
        }
        self.tag_list = QListWidget(self)
        for tag_id, name, _color in db_manager.get_all_tags():
            item = QListWidgetItem(name)
            item.setData(Qt.UserRole, tag_id)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if tag_id in current_ids else Qt.Unchecked)
            self.tag_list.addItem(item)
        if self.tag_list.count() == 0:
            self.tag_list.addItem("No tags yet — create your first one below")
            self.tag_list.item(0).setFlags(Qt.NoItemFlags)
        layout.addWidget(self.tag_list, 1)

        self.new_tag_input = LineEdit(self)
        self.new_tag_input.setPlaceholderText("Create a new tag (optional)")
        layout.addWidget(self.new_tag_input)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel, parent=self)
        buttons.accepted.connect(self._apply)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _apply(self):
        selected_ids = {
            int(item.data(Qt.UserRole))
            for index in range(self.tag_list.count())
            if (item := self.tag_list.item(index)).data(Qt.UserRole) is not None
            and item.checkState() == Qt.Checked
        }
        new_name = self.new_tag_input.text().strip()
        if new_name:
            tag_id = self.db_manager.add_tag(new_name)
            if tag_id is not None:
                selected_ids.add(tag_id)
        self.db_manager.set_tags_for_entry(self.entry_id, selected_ids, self.entry_type)
        self.accept()
