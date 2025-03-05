<div align="center">
  <h1>Clipboard Manager</h1>
</div>
<br>
<div align="center">
  <img src="https://img.shields.io/badge/python-3.6%2B-blue?logo=python&logoColor=white&style=for-the-badge" alt="Python Version">
  <img src="https://img.shields.io/badge/license-MIT-blue?style=for-the-badge" alt="License">
  <img src="https://img.shields.io/github/languages/code-size/NOTz00m/ClipboardManager?style=for-the-badge" alt="Code Size">
</div>
<br>
A lightweight, cross-platform, one-file clipboard manager built with Python and PySide6. It automatically saves your clipboard history, supports encryption (to be improved), and supports advanced search with wildcards—all in a modern, developer-friendly interface. Designed for programmers who frequently copy/paste code snippets and just need quick access to their clipboard history.

## Features
- Automatically stores clipboard history in a SQLite database.
- Supports encryption with an optional personal key/password.
- Advanced search functionality with wildcard support (e.g. use "type:code" to filter for code snippets).
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

Windows: To bundle the app into a standalone executable using PyInstaller, run:
```sh
pyinstaller --onefile --windowed --icon=clipboard.png --hidden-import PySide6 --hidden-import cryptography --hidden-import cryptography.fernet --add-data "pin.png;." --add-data "pin_active.png;." --add-data "star.png;." --add-data "JetBrainsMono-Regular.ttf;." --add-data "star_active.png;." --add-data "trash.png;." --add-data "clipboard.png;." clipboard_manager.py
```
Mac:
```sh
pyinstaller --onefile --windowed --icon=clipboard.png --hidden-import PySide6 --hidden-import cryptography --hidden-import cryptography.fernet --add-data "pin.png:." --add-data "pin_active.png:." --add-data "star.png:." --add-data "JetBrainsMono-Regular.ttf:." --add-data "star_active.png:." --add-data "trash.png:." --add-data "clipboard.png:." clipboard_manager.py
```
Alternatively, you can use cx_Freeze. Refer to its documentation for details on including additional data files.

## Future Plans

- Cloud Sync: Add support for syncing clipboard history across devices.

## Known Issues

- If the JetBrains Mono font is not found, the application falls back to a system monospace font.
- Dark Theme needs significant improvement.
- Currently working on getting false positive detections removed however it will take some time.

## Contributing

Contributions are welcome although they might be difficult! Please fork the repository and submit pull requests for improvements or bug fixes.
