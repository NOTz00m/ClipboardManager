def parse_shortcut(shortcut: str) -> tuple[set[str], str]:
    # parse shortcut string into modifiers and key
    aliases = {
        "control": "ctrl",
        "ctl": "ctrl",
        "option": "alt",
        "command": "meta",
        "cmd": "meta",
        "win": "meta",
        "windows": "meta",
    }
    parts = [aliases.get(part.strip().lower(), part.strip().lower()) for part in shortcut.split("+")]
    parts = [part for part in parts if part]
    if not parts:
        raise ValueError("Shortcut cannot be empty")
    modifiers = {part for part in parts if part in {"ctrl", "alt", "shift", "meta"}}
    keys = [part for part in parts if part not in modifiers]
    if len(keys) != 1:
        raise ValueError("Use modifier keys plus exactly one letter, number, or function key")
    return modifiers, keys[0]
