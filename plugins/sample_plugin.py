VERSION = '1.0.0'
DESCRIPTION = 'A sample plugin that adds a prefix to copied text'
AUTHOR = 'Clipboard Manager Team'

class SimplePrefixPlugin:
    def __init__(self):
        self.name = "Simple Prefix Plugin"
        self.enabled = True
        self.prefix = "🔔 "
        
    def on_clipboard_change(self, text):
        if not self.enabled:
            return text
            
        return f"{self.prefix}{text}"

def initialize():
    return SimplePrefixPlugin() 