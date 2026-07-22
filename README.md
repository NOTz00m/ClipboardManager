<div align="center">
  <h1>Clipboard Manager</h1>
  <p>A fast, local-first, encrypted clipboard history manager built with PySide6 & Fluent Design.</p>

  <img src="https://img.shields.io/badge/python-3.11%2B-blue?logo=python&logoColor=white&style=for-the-badge" alt="Python Version">
  <img src="https://img.shields.io/badge/license-MIT--Non--AI-blue?style=for-the-badge" alt="License">
  <img src="https://img.shields.io/badge/platform-Windows_10%2F11-0078D4?logo=windows&logoColor=white&style=for-the-badge" alt="Platform">
</div>

<br>

A lightweight desktop clipboard manager for Windows focused on speed, privacy, and clean developer workflows. Captures text and code clips in the background, encrypts data at rest, and provides instant searching and language detection.

## Features

- **Smart Deduplication**: Re-copying existing text moves it to the top of your history rather than creating duplicate rows, keeping your pins, stars, and tags attached.
- **Syntax-Based Content Detection**: Classifies code vs. text using syntax scoring for 15+ languages (Python, JS, C++, Rust, Go, SQL, JSON, etc.) and links instead of plain keyword matching.
- **Native Windows Hotkeys**: Uses native Win32 `RegisterHotKey` for zero-lag global toggle (`Ctrl+Alt+V` by default) without needing admin privileges.
- **Encryption at Rest**: Encrypts clipboard payloads locally using Fernet and salted PBKDF2. Encryption keys stay stored safely alongside your database.
- **Snippets & Tagging**: Save code clips as permanent snippets, tag items with custom colored chips, filter by language or type, and search through past clipboard history.
- **System Tray & Themes**: Minimizes to the system tray, supports dark/light/system themes, optional auto-start on boot, regex notifications, and opt-in Google Drive sync.

## Requirements

- **Python**: 3.11 or higher
- **OS**: Windows 10 or 11 (for native Win32 global hotkeys)

## Setup & Running

Install dependencies:

```powershell
pip install -r requirements.txt
```

Run from source:

```powershell
python main.py
```

On first run, a setup wizard configures your theme, encryption, retention policy, and startup options.

## Shortcuts & Controls

- **`Ctrl+Alt+V`**: Toggle window visibility from anywhere.
- **Window Close `[X]`**: Hides window to system tray while clipboard tracking remains active.
- **Tray Menu**: Right-click system tray icon -> **Exit** to shut down completely.

## Building Executable (.exe)

Build a standalone executable using the included PyInstaller spec:

```powershell
pip install pyinstaller
pyinstaller --clean ClipboardManager.spec
```

The output binary will be created in `dist/ClipboardManager.exe`.

> Note: To regenerate multi-resolution icon assets (`clipboard_manager.ico` and `clipboard.png`), run `python tools/generate_icons.py`.

## Running Tests

```powershell
python -m unittest discover -s tests -v
```

## Known Issues

- **Global Hotkey Conflicts**: If `Ctrl+Alt+V` (or your configured shortcut) is already registered by another application or Windows utility, registration will fail. A tray warning will pop up so you can bind a different shortcut in Settings.
- **Concurrent Clipboard Apps**: Running multiple clipboard managers simultaneously (such as Windows Clipboard `Win+V`) may occasionally cause win32 clipboard lock retries.

## Contributing

Contributions, bug reports, and feature requests are welcome!
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Commit your changes (`git commit -m 'Add new feature'`)
4. Push to the branch (`git push origin feature/my-feature`)
5. Open a Pull Request

Feel free to open an issue if you discover a bug or have ideas for improvements.

## License

Distributed under the **MIT NON-AI License**. See [LICENSE](LICENSE) for details.
