# GDPR Scanner

A Windows tray application that scans configured folders for Danish PII (CPR numbers, emails, phone numbers) in common file formats.

## Installation

1. Ensure Python 3.8+ is installed.
2. Clone or download the repository.
3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

## Running

1. Run the application:
   ```
   python -m src.main
   ```
2. The app starts in the system tray (no visible window).
3. Right-click the tray icon to open settings or start a scan.

## Configuration

- Use the "Åbn indstillinger" menu to configure scan folders, file types, age limits (0 for all files), and frequency.
- Settings are saved to `%APPDATA%\GDPRScanner\config.json`.

## Features

- Scans .txt, .log, .csv, .docx, .xlsx, .xls, .pdf files.
- Detects Danish CPR, emails (.dk), and phone numbers.
- Alerts for findings with options to delete, keep, or ignore permanently.
- Each alert shows a description of the GDPR violation.
- Option to abort the entire scan from any alert dialog.
- Scheduled or manual scans.

## Development

- Run tests: `pytest`
- Code in `src/`, tests in `tests/`.