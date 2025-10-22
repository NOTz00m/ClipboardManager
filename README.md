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
A modern, feature-rich clipboard manager built with Python and PySide6, designed to make your copy-paste workflow smoother with smart code detection, and powerful search capabilities. Perfect for developers who want quick access to their clipboard history with style!

## Features
- Modern UI with dark and light mode
- Smart code detection with advanced search filters
- Google Drive sync for cross-device access
- Built-in encryption for data security
- Extensible plugin system
- System tray integration with smart notifications

## Requirements
```
python >= 3.6
PySide6
cryptography
google-auth-oauthlib
google-api-python-client
```

## Installation
```sh
git clone https://github.com/NOTz00m/ClipboardManager.git
cd ClipboardManager
pip install -r requirements.txt
```

## Usage
```sh
python main.py
```
On first launch, our friendly setup wizard will help you configure everything just the way you like it!

## Building the Executable

### Windows
```sh
# Create a single executable with all features
pyinstaller ClipboardManager.spec
```

### macOS
```sh
# For macOS, use ':' instead of ';' in the --add-data paths
pyinstaller --name "ClipboardManager" --windowed --icon=clipboard.png --add-data "JetBrainsMono-Regular.ttf:." --add-data "clipboard.png:." --add-data "pin.png:." --add-data "pin_active.png:." --add-data "star.png:." --add-data "star_active.png:." --add-data "trash.png:." --hidden-import PySide6 --hidden-import cryptography --hidden-import cryptography.fernet --hidden-import google.auth.transport.requests --hidden-import google.oauth2.credentials --hidden-import google_auth_oauthlib.flow --hidden-import googleapiclient.discovery main.py
```

### Linux
```sh
# For Linux, use ':' instead of ';' in the --add-data paths (same as macOS)
pyinstaller ClipboardManager.spec
```

The executable will be created in the `dist` directory. For the best experience, we recommend using the spec file method as it includes all necessary dependencies and resources.

## Future Plans
- Mobile companion app
- Real-time sync across devices
- Custom themes support
- Custom keyboard shortcuts configuration
- Usage statistics and insights
- End-to-end encryption for cloud sync

## Known Issues
None at the moment! The recent update fixed the dark theme and scrollbar issues. If you find any bugs, please report them in the Issues section.

## Contributing
Love Clipboard Manager? We'd love your help! Whether it's reporting bugs, suggesting features, or contributing code - all contributions are welcome. Check out our issues page to get started!
