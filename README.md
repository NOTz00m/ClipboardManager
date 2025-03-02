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
git clone https://github.com/yourusername/clipboard-manager.git
cd clipboard-manager
pip install -r requirements.txt
