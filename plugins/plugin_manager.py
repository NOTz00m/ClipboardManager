import os
import sys
import importlib.util
import json
from PySide6.QtCore import QObject, Signal

class Plugin:
    def __init__(self, name, version, description, author):
        self.name = name
        self.version = version
        self.description = description
        self.author = author
        self.instance = None
        self.enabled = True
        
    def to_dict(self):
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "enabled": self.enabled
        }
        
    @classmethod
    def from_dict(cls, data):
        plugin = cls(
            name=data["name"],
            version=data["version"],
            description=data["description"],
            author=data["author"]
        )
        plugin.enabled = data.get("enabled", True)
        return plugin

class PluginManager(QObject):
    # signals for plugin events
    plugin_loaded = Signal(str)  # plugin_name
    plugin_unloaded = Signal(str)  # plugin_name
    
    def __init__(self, app_dir):
        super().__init__()
        self.app_dir = app_dir
        self.plugins = {}
        self.plugins_dir = os.path.join(app_dir, "plugins")
        self.load_plugin_config()
        self.scan_plugins()
        
    def load_plugin_config(self):
        config_path = os.path.join(self.app_dir, "plugin_config.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    config_data = json.load(f)
                    for plugin_data in config_data:
                        plugin = Plugin.from_dict(plugin_data)
                        self.plugins[plugin.name] = plugin
            except Exception as e:
                print(f"Failed to load plugin config: {e}")
                self.plugins = {}
                
    def save_plugin_config(self):
        config_path = os.path.join(self.app_dir, "plugin_config.json")
        config_data = [plugin.to_dict() for plugin in self.plugins.values()]
        with open(config_path, 'w') as f:
            json.dump(config_data, f, indent=4)
            
    def scan_plugins(self):
        if not os.path.exists(self.plugins_dir):
            os.makedirs(self.plugins_dir)
            
        # add plugins directory to python path
        if self.plugins_dir not in sys.path:
            sys.path.append(self.plugins_dir)
            
        # scan for plugin files
        for filename in os.listdir(self.plugins_dir):
            if filename.endswith('.py') and not filename.startswith('__'):
                plugin_name = filename[:-3]
                if plugin_name not in self.plugins:
                    try:
                        # load plugin module
                        spec = importlib.util.spec_from_file_location(
                            plugin_name,
                            os.path.join(self.plugins_dir, filename)
                        )
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        
                        # create plugin instance
                        plugin = Plugin(
                            name=plugin_name,
                            version=getattr(module, 'VERSION', '1.0.0'),
                            description=getattr(module, 'DESCRIPTION', ''),
                            author=getattr(module, 'AUTHOR', 'Unknown')
                        )
                        
                        # initialize plugin
                        if hasattr(module, 'initialize'):
                            plugin.instance = module.initialize()
                            
                        self.plugins[plugin_name] = plugin
                        self.plugin_loaded.emit(plugin_name)
                    except Exception as e:
                        print(f"Failed to load plugin {plugin_name}: {e}")
                        
    def enable_plugin(self, name):
        if name in self.plugins:
            plugin = self.plugins[name]
            if not plugin.enabled:
                plugin.enabled = True
                self.save_plugin_config()
                return True
        return False
        
    def disable_plugin(self, name):
        if name in self.plugins:
            plugin = self.plugins[name]
            if plugin.enabled:
                plugin.enabled = False
                self.save_plugin_config()
                return True
        return False
        
    def get_plugin(self, name):
        return self.plugins.get(name)
        
    def get_enabled_plugins(self):
        return [plugin for plugin in self.plugins.values() if plugin.enabled]
        
    def call_plugin_method(self, plugin_name, method_name, *args, **kwargs):
        plugin = self.plugins.get(plugin_name)
        if plugin and plugin.enabled and plugin.instance:
            method = getattr(plugin.instance, method_name, None)
            if method:
                return method(*args, **kwargs)
        return None 