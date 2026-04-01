# Technology Stack

**Project:** GDPR Scanner (Python Windows system tray file scanner)
**Researched:** 2026-04-01
**Note:** External web tools unavailable. All findings from training knowledge (cutoff August 2025). Version numbers reflect last known stable release — verify with `pip index versions <package>` before pinning.

---

## Recommended Stack

### System Tray

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| pystray | 0.19.x | Windows system tray icon and menu | Only actively maintained pure-Python tray library. Cross-platform but Windows-first in practice. PIL/Pillow for icon rendering. Simple API: `Icon`, `Menu`, `MenuItem`. No native win32 dependency required. |
| Pillow | 10.x | Tray icon image rendering | Required by pystray for icon objects. Also useful for generating a simple colored PNG icon at runtime without bundling asset files. |

**Confidence: HIGH** — pystray is the de-facto standard; no credible alternative exists in pure Python for Windows tray. Last known release 0.19.5 (2023), project still receives maintenance.

**Why not win32api/win32gui directly:** Requires pywin32, adds ~10 MB, and the raw Win32 tray API is error-prone. pystray wraps it correctly.

**Why not infi.systray:** Abandoned, Windows-only, no updates since ~2018.

**Why not rumps:** macOS only.

---

### GUI (Configuration Dialog)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| tkinter | stdlib (Python 3.11+) | Config dialog, alert dialogs, folder picker | Zero dependencies, ships with Python, sufficient for simple forms. `ttk` widgets give a modern-enough look on Windows 11. `filedialog.askdirectory()` covers folder selection without extra libs. |

**Confidence: HIGH** — PROJECT.md already mandates tkinter. Validated: for a single-user config dialog with checkboxes, folder pickers, and spinboxes, tkinter is the right call. Adding PyQt5/6 or wxPython for this use case would bring 30-60 MB of extra dependencies for no UX gain.

**Why not PyQt6:** License (GPL) is problematic for distribution unless project is open-source. PyQt5 is LGPL but still ~40 MB added to bundle. Overkill for a config dialog.

**Why not customtkinter:** Adds a dependency for marginal visual improvement. Not worth it.

**Why not wx/wxPython:** Large, slow to install, no advantage here.

**Threading note:** pystray runs on a background thread; tkinter must run on the main thread. The canonical pattern is: pystray in a daemon thread, tkinter root on main thread, with `root.after()` / `queue.Queue` for cross-thread communication. This is a known pattern and well-documented.

---

### File Content Reading

| Library | Version | File Types | Why |
|---------|---------|-----------|-----|
| python-docx | 1.1.x | .docx | Official python-docx successor (maintained by same author). Extracts paragraph text and table cell text. Clean API. Note: does NOT handle legacy .doc (binary Word) — see pitfalls. |
| openpyxl | 3.1.x | .xlsx, .xls (read-only via compatibility) | Standard library for xlsx. `read_only=True` mode is critical for large files — prevents loading entire workbook into RAM. Iterates rows without buffering. |
| csv (stdlib) | stdlib | .csv | Built-in. Use `csv.reader` with `encoding='utf-8-sig'` to handle BOM-prefixed files from Excel exports. No external dependency needed. |
| pdfplumber | 0.10.x | .pdf | Best balance of accuracy and simplicity for text extraction. Built on pdfminer.six. Handles multi-column layouts better than PyPDF2. Returns text per page, supports table extraction. |
| chardet | 5.x | .txt, .log | Encoding detection for plain text files. Danish files often arrive as Windows-1252 or ISO-8859-1. Wrap all `open()` calls with chardet detection before assuming UTF-8. |

**Confidence: HIGH** for python-docx, openpyxl, csv. **MEDIUM** for pdfplumber (solid choice but PyMuPDF is a strong alternative — see below).

**Why pdfplumber over PyPDF2:** PyPDF2 has notoriously poor text extraction on non-trivial PDFs (merged characters, missing spaces). pdfplumber uses pdfminer under the hood and produces cleaner output for Danish business documents.

**Why pdfplumber over PyMuPDF (fitz):** PyMuPDF is faster and more accurate but has a GPL/AGPL license concern and a more complex install (native binary). For a single-user personal tool, pdfplumber's pure-Python install is simpler and "good enough." If scan accuracy on complex PDFs proves insufficient, migrate to PyMuPDF.

**Why not textract:** Depends on external command-line tools (antiword, pdftotext) that must be separately installed. Not viable for a self-contained Windows app.

**Legacy .doc files:** python-docx cannot open binary .doc format. Options: (a) skip .doc entirely in v1 (recommended — low prevalence on modern systems), (b) use win32com automation via pywin32 (requires Word installed), (c) use antiword/LibreOffice headless (external dependency). Recommend: skip .doc in v1, document as known limitation.

---

### Pattern Matching / GDPR Detection

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| re (stdlib) | stdlib | CPR, email, phone regex scanning | Python's built-in `re` module is sufficient. For GDPR patterns, regex is deterministic and fast. No external NLP library needed (PROJECT.md explicitly rules out ML/NLP). |

**Confidence: HIGH** — re is the right tool. The patterns are well-defined:

- **CPR numbers:** `\b\d{6}[-\s]?\d{4}\b` — matches DDMMYY-XXXX and DDMMYYXXXX. Add Luhn-like checksum validation via the modulus-11 rule to reduce false positives (CPR numbers have a deterministic check digit for numbers issued before 2007; newer ones do not — document this caveat).
- **Email addresses:** Standard RFC-loose pattern, e.g. `[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}` is sufficient.
- **Danish phone numbers:** `(\+45[\s\-]?)?(\d{2}[\s\-]?){4}` — 8-digit Danish numbers with optional +45 prefix.
- **Column headers:** Simple string matching against a whitelist (`['navn', 'adresse', 'cpr', 'fødselsdato', 'personnummer', 'kaldenavn', 'patient', 'kunde']`) on lowercase-normalized header rows.

**Why not regex library (PyPI):** The `regex` package adds features like variable-length lookbehind, not needed here. Adds a dependency for no gain.

**Why not spaCy/NLTK:** Explicitly out of scope per PROJECT.md. Adds 500 MB+ dependencies.

---

### Settings / Config Persistence

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| json (stdlib) | stdlib | Config file, ignore list | Simple, human-readable, no schema enforcement needed. Python's built-in `json` module handles read/write. Store at `%APPDATA%\GDPRScanner\config.json` and `ignore_list.json`. |
| pathlib (stdlib) | stdlib | Path construction | `pathlib.Path(os.environ['APPDATA']) / 'GDPRScanner'` for cross-session config location. |

**Confidence: HIGH** — JSON + stdlib is the right choice for a single-user personal tool. PROJECT.md mandates this.

**Config file location:** Use `%APPDATA%\GDPRScanner\` (i.e., `C:\Users\<user>\AppData\Roaming\GDPRScanner\`), not next to the executable. This survives reinstallation and works correctly when bundled with PyInstaller.

**Why not configparser / INI:** JSON handles nested structures (list of folders, list of ignored files) more cleanly than INI sections. No advantage to INI here.

**Why not SQLite:** Overkill. The ignore list is a simple array of file paths. JSON is sufficient and human-inspectable.

**Why not platformdirs:** The `platformdirs` package provides `user_data_dir()` cross-platform, but for a Windows-only tool, directly using `os.environ['APPDATA']` is simpler with zero dependencies.

---

### Packaging / Distribution

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| PyInstaller | 6.x | Bundle to single .exe or one-dir package | Industry standard for Python Windows packaging. `--onefile` produces a single .exe; `--onedir` (default) produces a folder — onedir is faster to start and easier to debug. For personal use, onedir is preferred. |

**Confidence: HIGH** — PyInstaller 6.x is the current standard. Well-maintained, large community, good Windows support.

**Recommended PyInstaller flags:**
```
pyinstaller main.py
  --name GDPRScanner
  --windowed          # no console window (critical for tray app)
  --onedir            # faster startup than --onefile
  --icon icon.ico     # embed icon
  --add-data "icon.png;."  # bundle any asset files
```

**Why not --onefile for tray apps:** `--onefile` extracts to a temp directory on each launch, causing a 2-5 second delay before the tray icon appears. For a background tray app that may start at login, this is noticeable. Use `--onedir`.

**Why not cx_Freeze:** Still maintained but PyInstaller has better community support, more plugins (e.g. for pdfplumber/pdfminer hook fixes), and more StackOverflow answers. cx_Freeze is a valid alternative but offers no advantage here.

**Why not Nuitka:** Compiles Python to C for true single-binary output with no extraction delay. More complex build setup, longer compile times. Worth considering for v2 if startup time is a complaint, but overkill for initial release.

**Why not py2exe:** Effectively abandoned. Last meaningful update was years ago.

**PyInstaller hook note:** pdfminer/pdfplumber may require a custom `.spec` file entry for hidden imports (`pdfminer.pdfparser`, `pdfminer.pdfdocument`, etc.). This is a known packaging pitfall — document in PITFALLS.md.

**Auto-start at Windows login:** Use the Windows registry (`HKCU\Software\Microsoft\Windows\CurrentVersion\Run`) via the `winreg` stdlib module. No external dependency needed. Add as optional setting in config dialog.

---

## Full Dependency List

```
# requirements.txt
pystray>=0.19.5
Pillow>=10.0.0
python-docx>=1.1.0
openpyxl>=3.1.2
pdfplumber>=0.10.0
chardet>=5.2.0

# Dev / build only
pyinstaller>=6.0.0
```

**Total install size (approximate):** ~80-100 MB in site-packages. Bundled onedir: ~120-150 MB. Acceptable for a personal desktop tool.

**Python version:** Target Python 3.11 or 3.12. Both are current LTS-track releases as of 2025. Avoid 3.13 for now — some binary dependencies (openpyxl, pdfplumber) may lag behind on wheels. Python 3.11 is the safest target for PyInstaller compatibility.

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| System tray | pystray | infi.systray | Abandoned since ~2018 |
| System tray | pystray | win32gui direct | 10 MB pywin32 dep, complex raw API |
| GUI | tkinter | PyQt6 | GPL license, 40 MB overhead, overkill |
| GUI | tkinter | customtkinter | Extra dep for cosmetic gain only |
| GUI | tkinter | wxPython | Large, slow install, no advantage |
| .pdf reading | pdfplumber | PyPDF2 | Poor text extraction quality |
| .pdf reading | pdfplumber | PyMuPDF | License complexity, native binary |
| .pdf reading | pdfplumber | textract | Requires external CLI tools |
| .doc reading | (skip v1) | win32com | Requires Word installed |
| Config | json stdlib | configparser | Can't handle nested lists cleanly |
| Config | json stdlib | SQLite | Overkill for simple key-value + list |
| Config location | %APPDATA% | beside .exe | Breaks on reinstall, UAC issues |
| Packaging | PyInstaller | cx_Freeze | Smaller community, fewer hooks |
| Packaging | PyInstaller | Nuitka | Complex build, overkill for v1 |
| Packaging | PyInstaller onedir | PyInstaller onefile | Slow extraction delay on each start |

---

## Confidence Summary

| Area | Confidence | Reason |
|------|------------|--------|
| pystray | HIGH | De-facto standard, no credible alternative, well-known API |
| tkinter | HIGH | Stdlib, zero risk, aligns with project constraints |
| python-docx | HIGH | Canonical library, actively maintained |
| openpyxl | HIGH | Canonical library, actively maintained |
| csv stdlib | HIGH | Stdlib, no alternatives needed |
| pdfplumber | MEDIUM | Good choice; PyMuPDF is faster/more accurate but license tradeoff |
| chardet | HIGH | Standard encoding detection library |
| re stdlib | HIGH | Stdlib, regex patterns are deterministic for this domain |
| json stdlib | HIGH | Stdlib, aligns with project constraints |
| PyInstaller 6.x | HIGH | Industry standard, large community |
| Python 3.11 target | MEDIUM | Safe choice as of Aug 2025; 3.12 also viable, 3.13 riskier |

**Note:** Version numbers not independently verified against PyPI (external tools unavailable). All are best-known-stable as of training cutoff August 2025. Run `pip install <package>` without pinning during development to get latest compatible versions, then pin for distribution.
