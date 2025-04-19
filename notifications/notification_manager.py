from PySide6.QtWidgets import QSystemTrayIcon
from PySide6.QtCore import QObject, Signal
import json
import os
import re
from datetime import datetime

class NotificationRule:
    def __init__(self, name, pattern, enabled=True):
        self.name = name
        self.pattern = pattern
        self.enabled = enabled
        self.compiled_pattern = re.compile(pattern, re.IGNORECASE)
        
    def matches(self, text):
        return self.enabled and bool(self.compiled_pattern.search(text))
        
    def to_dict(self):
        return {
            "name": self.name,
            "pattern": self.pattern,
            "enabled": self.enabled
        }
        
    @classmethod
    def from_dict(cls, data):
        return cls(
            name=data["name"],
            pattern=data["pattern"],
            enabled=data["enabled"]
        )

class NotificationManager(QObject):
    # signal emitted when a notification rule is triggered
    notification_triggered = Signal(str, str)  # rule_name, matched_text
    
    def __init__(self, app_dir):
        super().__init__()
        self.app_dir = app_dir
        self.rules = []
        self.tray_icon = None
        self.load_rules()
        
    def set_tray_icon(self, tray_icon):
        self.tray_icon = tray_icon
        
    def load_rules(self):
        rules_path = os.path.join(self.app_dir, "notification_rules.json")
        if os.path.exists(rules_path):
            try:
                with open(rules_path, 'r') as f:
                    rules_data = json.load(f)
                    self.rules = [NotificationRule.from_dict(rule) for rule in rules_data]
            except Exception:
                self.rules = []
        else:
            # default rules
            self.rules = [
                NotificationRule("Code Snippet", r"```[\s\S]*?```"),
                NotificationRule("URL", r"https?://\S+"),
                NotificationRule("Email", r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
            ]
            self.save_rules()
            
    def save_rules(self):
        rules_path = os.path.join(self.app_dir, "notification_rules.json")
        rules_data = [rule.to_dict() for rule in self.rules]
        with open(rules_path, 'w') as f:
            json.dump(rules_data, f, indent=4)
            
    def add_rule(self, name, pattern):
        rule = NotificationRule(name, pattern)
        self.rules.append(rule)
        self.save_rules()
        return rule
        
    def remove_rule(self, name):
        self.rules = [rule for rule in self.rules if rule.name != name]
        self.save_rules()
        
    def toggle_rule(self, name):
        for rule in self.rules:
            if rule.name == name:
                rule.enabled = not rule.enabled
                self.save_rules()
                return rule.enabled
        return False
        
    def check_text(self, text):
        if not self.tray_icon or not text:
            return
            
        for rule in self.rules:
            if rule.matches(text):
                # truncate text for notification
                display_text = text[:100] + "..." if len(text) > 100 else text
                self.tray_icon.showMessage(
                    "Clipboard Manager",
                    f"Matched {rule.name}: {display_text}",
                    QSystemTrayIcon.Information,
                    3000
                )
                self.notification_triggered.emit(rule.name, text)
                break 