from __future__ import annotations

import sys

from PySide6.QtCore import QAbstractNativeEventFilter, QCoreApplication, QObject, Signal
from shortcut_parser import parse_shortcut


class _WindowsNativeFilter(QAbstractNativeEventFilter):
    def __init__(self, callback, hotkey_id, message_id):
        super().__init__()
        self.callback = callback
        self.hotkey_id = hotkey_id
        self.message_id = message_id

    def nativeEventFilter(self, event_type, message):
        if sys.platform == "win32":
            import ctypes.wintypes

            try:
                msg = ctypes.wintypes.MSG.from_address(int(message))
                if msg.message == self.message_id and msg.wParam == self.hotkey_id:
                    self.callback()
                    return True
            except (TypeError, ValueError):
                pass
        return False


class GlobalHotkeyManager(QObject):
    # global hotkeys using RegisterHotKey on win32

    activated = Signal()

    _HOTKEY_ID = 0xC1A0
    _WM_HOTKEY = 0x0312
    _MODIFIERS = {"alt": 0x0001, "ctrl": 0x0002, "shift": 0x0004, "meta": 0x0008}
    _MOD_NOREPEAT = 0x4000

    def __init__(self, parent=None):
        super().__init__(parent)
        self._bound = False
        self._fallback_handle = None
        self._native_filter = _WindowsNativeFilter(
            self.activated.emit, self._HOTKEY_ID, self._WM_HOTKEY
        )
        QCoreApplication.instance().installNativeEventFilter(self._native_filter)

    @staticmethod
    def _virtual_key(key: str) -> int:
        if len(key) == 1 and key.isalpha():
            return ord(key.upper())
        if len(key) == 1 and key.isdigit():
            return ord(key)
        if key.startswith("f") and key[1:].isdigit() and 1 <= int(key[1:]) <= 24:
            return 0x70 + int(key[1:]) - 1
        named = {
            "space": 0x20,
            "tab": 0x09,
            "escape": 0x1B,
            "esc": 0x1B,
            "home": 0x24,
            "end": 0x23,
            "pageup": 0x21,
            "pagedown": 0x22,
            "insert": 0x2D,
        }
        if key in named:
            return named[key]
        raise ValueError(f"Unsupported shortcut key: {key}")

    def bind(self, shortcut: str) -> tuple[bool, str]:
        self.unbind()
        try:
            modifiers, key = parse_shortcut(shortcut)
        except ValueError as exc:
            return False, str(exc)

        if sys.platform == "win32":
            import ctypes

            modifier_mask = self._MOD_NOREPEAT
            for modifier in modifiers:
                modifier_mask |= self._MODIFIERS[modifier]
            try:
                virtual_key = self._virtual_key(key)
            except ValueError as exc:
                return False, str(exc)
            if not ctypes.windll.user32.RegisterHotKey(None, self._HOTKEY_ID, modifier_mask, virtual_key):
                return False, "That shortcut is already in use by Windows or another app"
            self._bound = True
            return True, ""

        try:
            import keyboard

            self._fallback_handle = keyboard.add_hotkey(
                shortcut,
                self.activated.emit,
                suppress=False,
                trigger_on_release=True,
            )
            self._bound = True
            return True, ""
        except Exception as exc:
            return False, str(exc)

    def unbind(self):
        if sys.platform == "win32" and self._bound:
            import ctypes

            ctypes.windll.user32.UnregisterHotKey(None, self._HOTKEY_ID)
        elif self._fallback_handle is not None:
            try:
                import keyboard

                keyboard.remove_hotkey(self._fallback_handle)
            except Exception:
                pass
        self._bound = False
        self._fallback_handle = None

    def close(self):
        self.unbind()
        app = QCoreApplication.instance()
        if app is not None:
            app.removeNativeEventFilter(self._native_filter)
