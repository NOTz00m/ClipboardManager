# Clipboard Manager

A lightweight, cross-platform clipboard manager built with Python and PySide6. It automatically saves your clipboard history, encrypts sensitive data, and supports advanced search with wildcards—all in a modern, developer-friendly interface. Designed for programmers who frequently copy/paste code snippets and need quick access to their clipboard history.

## Features
- Automatically stores clipboard history in a SQLite database.
- Supports encryption with an optional personal key/password.
- Advanced search functionality with wildcard support (e.g. use "[code]" to filter for code snippets).
- Customizable dark/light themes.
- Cross-platform compatibility (Windows, macOS, Linux).
- Easy to build and bundle as a standalone executable.

## Requirements
- Python 3.6+
- PySide6
- cryptography

## Installation
```sh
git clone https://github.com/NOTz00m/ClipboardManager.git
cd clipboard-manager
pip install -r requirements.txt
```

## Usage
```sh
python clipboard_manager.py
```

On first run, a startup wizard will guide you through the initial setup (encryption options, theme selection, etc.).

## Building as an Executable

To bundle the app into a standalone executable using PyInstaller, run:
```sh
pyinstaller --onefile --noconsole --add-data "clipboard.png:." --add-data "JetBrainsMono-Regular.ttf:." --hidden-import PySide6.QtGui --hidden-import PySide6.QtWidgets --hidden-import PySide6.QtCore clipboard_manager.py
```
Make sure to include the following files in your build:
- clipboard.png (for the tray icon)
- JetBrainsMono-Regular.ttf (the font file)
Alternatively, you can use cx_Freeze. Refer to its documentation for details on including additional data files.

## Contributing

Contributions are welcome! Please fork the repository and submit pull requests for improvements or bug fixes.
