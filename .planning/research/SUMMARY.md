# Project Research Summary

**Project:** GDPR Scanner
**Domain:** Python Windows system tray app — personal GDPR compliance / PII file discovery
**Researched:** 2026-04-01
**Confidence:** HIGH (all core decisions backed by stable, well-documented library constraints)

---

## Executive Summary

This is a single-user, Windows-only background scanning tool written in Python that monitors local folders for files containing Danish personal data (CPR numbers, emails, phone numbers, and PII-indicating column headers). The expert approach for this category of tool is well established: a system tray daemon built on `pystray`, a lightweight `tkinter` config dialog, a regex-based detection engine (no ML), and JSON persistence in `%APPDATA%`. The user's chosen tech stack exactly matches what research recommends — there are no technology pivots needed.

The central architectural constraint that drives every design decision is this: `pystray` must own the main thread on Windows (Win32 message pump requirement), which forces `tkinter` onto a worker thread and all cross-thread communication through a `queue.Queue`. This is a hard constraint, not a preference — violating it causes silent menu failures and tray icon disappearance. All other design choices flow from this single fact.

The primary risks are operational, not conceptual: (1) CPR pattern false positives are the single biggest trust-breaker — phone numbers and order IDs match the same 10-digit format, requiring date validation and column-context suppression to stay clean; (2) malformed Office files and large PDFs will crash naive scan loops — every file parse must be wrapped in per-file exception handling; (3) JSON config files can corrupt on unclean Windows shutdown and must use atomic writes. These risks are all well-understood and have proven prevention patterns.

---

## Key Findings

### Recommended Stack

The full stack is stdlib-first with a minimal set of well-maintained third-party libraries. `pystray` (0.19.x) is the only viable Python tray library for Windows — no credible alternative exists. `tkinter` (stdlib) is the correct GUI choice: zero dependencies, sufficient for a config dialog with checkboxes and folder pickers. File parsing uses `python-docx`, `openpyxl`, `pdfplumber`, and `chardet` — all canonical choices. Detection uses only Python's built-in `re` module; the patterns are deterministic and NLP is explicitly out of scope. Config persistence is plain JSON to `%APPDATA%\GDPRScanner\`. Packaging is PyInstaller 6.x `--onedir` (not `--onefile` — extraction delay on each launch is unacceptable for a tray app). Target Python 3.11.

**Core technologies:**
- `pystray 0.19.x`: system tray icon and menu — de-facto standard, no alternative
- `tkinter` (stdlib): config dialog and alert dialogs — zero dependencies, sufficient for this use case
- `python-docx 1.1.x`: .docx reading — canonical library, actively maintained
- `openpyxl 3.1.x`: .xlsx reading — canonical library, use `read_only=True` for large files
- `pdfplumber 0.10.x`: .pdf text extraction — best pure-Python option; PyMuPDF is faster but license-complex
- `chardet 5.x`: encoding detection for .txt/.log — needed for Danish Windows-1252 files
- `re` (stdlib): GDPR pattern matching — deterministic regex, no NLP
- `json` (stdlib): config and ignore-list persistence — human-readable, no DB needed
- `PyInstaller 6.x` (build only): Windows .exe packaging — use `--onedir`, not `--onefile`

See `.planning/research/STACK.md` for full rationale and alternatives considered.

### Expected Features

The feature set maps cleanly to what compliance scanning tools provide. Detection quality (low false positive rate) is the single most important attribute — one bad alert trains users to dismiss everything.

**Must have (table stakes):**
- CPR number detection with date-validity check (not mod-11 alone — post-2007 CPRs do not conform)
- Email address detection — low false positive risk, standard pattern
- Danish phone number detection — require `+45` prefix or space-separated pair format to reduce FPs
- Filename/directory keyword matching — fast pre-filter before expensive content parsing
- Column header heuristics in CSV/XLSX — `CPR`, `Navn`, `Adresse`, `Fødselsdato`, `Telefon` etc.
- .txt, .csv, .docx, .xlsx, .pdf content scanning
- File age threshold filter (default 30 days, configurable)
- Alert dialog: Delete / Keep / Ignore permanent
- Ignore list persisted to JSON
- Folder selection (multiple folders)
- Tray icon with right-click menu (Settings, Scan Now, Exit)
- Configurable scan frequency
- Settings persisted between sessions (`%APPDATA%\GDPRScanner\config.json`)
- Windows startup registration (registry key via `winreg`)

**Should have (differentiators):**
- Scan summary log ("last scan: 14 files checked, 2 flagged")
- Context snippet in alert dialog (show ~80 chars around match, partial masking)
- Column header match reporting ("Column 'CPR-nr' triggered flag")
- File size guard before parsing (skip files over configurable threshold)
- Tray icon status change when violations found

**Defer to v2+:**
- Ignore by content hash (path-based ignore covers 80% of cases for v1)
- Scan progress indicator (spinning icon acceptable for v1)
- Export findings to CSV
- .eml / .msg email file scanning
- Legacy .doc / .xls format support
- ZIP/archive scanning

See `.planning/research/FEATURES.md` for full feature dependency graph and Danish pattern reference.

### Architecture Approach

The architecture is forced by the pystray main-thread constraint into a three-thread model: pystray on the main thread, tkinter on a persistent daemon thread, and a single sequential scanner thread. All cross-thread communication passes through one `queue.Queue` carrying typed dataclass events (`FindingEvent`, `OpenConfigEvent`, `ShutdownEvent`). The tkinter thread polls the queue every 100ms via `root.after()` — never blocking `queue.get()`. The scan pipeline is structured as four discrete pure-function stages (filter, read, detect, emit) that are independently testable without spinning up the full application.

**Major components:**
1. `TrayApp` — owns pystray icon and menu on main thread; dispatches to UI via queue; never touches tkinter
2. `UIThread` — owns the single `tk.Tk()` root; all dialogs are `Toplevel` children; polls queue via `after(100)`
3. `ScanPipeline` — four-stage pipeline: `filter_files()` → `read_content()` → `scan_for_pii()` → `emit()`
4. `ScanScheduler` — triggers scan cycles on a timer; single daemon thread; not a thread pool
5. `ConfigStore` — reads/writes `config.json` and `ignore.json`; passed by dependency injection; not a singleton
6. `FindingQueue` — `queue.Queue` instance shared across all components; the single IPC channel

**Critical threading rules:**
- `pystray.Icon.run()` must be called from `main()` on the main thread
- All tkinter widget creation and method calls must happen on the UI thread
- Queue polling uses `get_nowait()` + `try/except Empty` — never blocking `get()`
- One `tk.Tk()` instance per process; additional windows are `tk.Toplevel`

See `.planning/research/ARCHITECTURE.md` for full component map, data flow diagrams, and anti-patterns.

### Critical Pitfalls

1. **pystray on non-main thread** — Menu callbacks silently fail, icon vanishes after sleep/wake. Prevention: `icon.run()` on main thread always; tkinter on worker thread; all tkinter calls marshalled via `root.after()`.

2. **tkinter called from wrong thread** — `RuntimeError: main thread is not in main loop` or silent crashes. Prevention: every tkinter operation goes through the queue and is executed on the UI thread only.

3. **CPR false positives from phone/order numbers** — Phone numbers and 10-digit IDs match the CPR regex. Prevention: validate date component (`DD` 01-31, `MM` 01-12); use column-header context to suppress in obvious non-CPR columns; do NOT rely on mod-11 checksum alone (post-2007 CPRs fail it).

4. **Malformed Office files crashing the scan loop** — Real `.docx`/`.xlsx` from LibreOffice/Google Docs exports or password-protected files raise `BadZipFile`, `KeyError`, `XMLSyntaxError`. Prevention: wrap every file parse in `try/except Exception` per file; add file-size guard before opening.

5. **pdfplumber memory exhaustion on large PDFs** — 200-page image-heavy PDF can consume 500MB–1GB RAM. Prevention: skip PDFs over 20–30 MB; extract page-by-page with early exit; cap at first 10 pages.

6. **JSON config corruption on unclean shutdown** — Partial write leaves unparseable JSON. Prevention: write to `.tmp` then `os.replace()` (atomic rename on NTFS); catch `JSONDecodeError` on startup and fall back to defaults.

7. **PyInstaller missing hidden imports** — Packaged `.exe` crashes with `ModuleNotFoundError` on `pystray._win32`, pdfminer submodules, Pillow backends. Prevention: maintain a `.spec` file with explicit `hiddenimports`; use `--collect-all pdfplumber`; test on a clean VM.

See `.planning/research/PITFALLS.md` for full pitfall list including CSV encoding, openpyxl phantom cells, Windows file locking, and shutdown thread joining.

---

## Implications for Roadmap

Based on research, the natural phase structure follows component dependency order from ARCHITECTURE.md, with pitfall risk informing phase boundaries.

### Phase 1: Core Scaffolding — Tray + Config + Persistence

**Rationale:** Everything else depends on config being loadable and the tray/tkinter threading model being correct. Get the hard architectural constraint (main-thread pystray) right first, before any scan logic exists to complicate debugging.

**Delivers:** A working system tray app that starts at login, shows a tray icon, opens a config dialog, and persists settings — no scanning yet. This is the skeleton that all subsequent phases slot into.

**Addresses:** Folder selection, scan frequency config, file age threshold config, settings persistence, Windows startup registration, tray right-click menu.

**Avoids:** pystray main-thread pitfall (Pitfall 1), tkinter wrong-thread pitfall (Pitfall 2), JSON corruption pitfall (Pitfall 6), shutdown thread-join pitfall (Pitfall 16).

**Research flag:** Standard patterns — skip phase research. The threading model is well-documented and fully specified in ARCHITECTURE.md.

### Phase 2: Scan Pipeline — File Filtering and Content Extraction

**Rationale:** With config working, build the scan pipeline stage by stage. Start with the simplest file types (txt/csv) before tackling Office formats and PDF. Each extractor is independently testable. No UI changes needed — findings go to the queue but can be logged to console until Phase 3's alert dialog.

**Delivers:** A scanner that walks configured folders, applies age/type filters, extracts text from supported formats, and emits findings to the queue. CPR, email, and phone detection included. Column header heuristics for CSV/XLSX.

**Addresses:** .txt, .csv, .docx, .xlsx, .pdf content scanning; CPR/email/phone detection; filename keyword matching; column header heuristics; file size guard.

**Avoids:** File locking on Windows (Pitfall 3), malformed file crashes (Pitfall 4), pdfplumber memory exhaustion (Pitfall 5), CPR false positives from phone numbers (Pitfall 7), openpyxl phantom cell iteration (Pitfall 9), CSV encoding errors (Pitfall 13), symlink loops (Pitfall 14), .doc confusion with python-docx (Pitfall 15).

**Research flag:** CPR post-2007 modulus-11 behavior needs verification against CPR-kontoret official documentation before shipping this phase.

### Phase 3: Alert Dialog and Ignore List

**Rationale:** With findings flowing from Phase 2, wire up the user decision loop. The queue-gated single-dialog pattern (Option A from ARCHITECTURE.md) maps directly onto the existing architecture. Ignore list persistence is a simple JSON append.

**Delivers:** Alert dialog (Delete / Keep / Ignore permanent), ignore list persisted to JSON, tray icon status change when violations found, scan summary logging.

**Addresses:** Alert dialog with action choices, ignore list persistence, context snippet in alert dialog, column header match reporting.

**Avoids:** Multiple `tk.Tk()` instances (Pitfall 2 variant — use `Toplevel`), queue blocking from UI thread (queue polling pattern already established in Phase 1).

**Research flag:** Standard patterns — skip phase research.

### Phase 4: Packaging and Distribution

**Rationale:** Final phase turns the working script into a distributable `.exe`. Known PyInstaller hidden-import issues for this exact stack are fully documented and require a maintained `.spec` file.

**Delivers:** `GDPRScanner` onedir package with embedded icon, no console window, tested on a clean Windows VM.

**Addresses:** PyInstaller packaging; `--onedir` (not `--onefile`); hidden imports for pystray._win32, pdfminer, Pillow.

**Avoids:** Missing hidden imports crash (Pitfall 11), Windows Defender false positive flags from `--onefile` (Pitfall 17).

**Research flag:** Verify PyInstaller hidden imports empirically — test on a clean VM with no Python installed. The spec file entries in PITFALLS.md are a starting point, not a guarantee.

### Phase Ordering Rationale

- Phase 1 before everything: the threading model is the foundation; getting it wrong means refactoring the entire app
- Phase 2 before Phase 3: scan pipeline must produce findings before alert dialog has anything to show
- Phase 3 before Phase 4: no point packaging until the full user loop (find → decide → ignore) is working
- PDF scanning deferred to late Phase 2: significantly more complex and resource-intensive than text/Office formats; add after core is stable
- Packaging isolated to its own phase: packaging bugs are distinct from application bugs; keeping them separate avoids confusion

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All choices are stdlib or de-facto standards with no credible alternatives. Version numbers from training data (Aug 2025) — verify with pip before pinning. |
| Features | HIGH (detection patterns) / MEDIUM (UI conventions) | CPR/email/phone patterns are stable and deterministic. UI expectations based on pattern knowledge of comparable tools, not current user research. |
| Architecture | HIGH | Threading constraints are forced by library implementation, not preference. Queue/after() polling pattern is well-established. |
| Pitfalls | HIGH (most) / MEDIUM (CPR mod-11 cutoff) | Windows file locking, encoding, PyInstaller hidden imports are all well-documented. CPR post-2007 behavior needs official source verification. |

**Overall confidence:** HIGH

### Gaps to Address

- **CPR mod-11 post-2007 behavior:** Training data says checksum was abandoned for numbers issued after ~2007, but the exact cutoff and century-digit encoding rules should be verified against CPR-kontoret official documentation before shipping Phase 2. Use date validation + century digit check as the primary filter; treat mod-11 as a confidence booster only.

- **pystray WM_TASKBARCREATED handling:** Whether current pystray (0.19.x) auto-handles Explorer shell restarts is unclear from training data. Verify against pystray changelog before closing Phase 3. Low priority for personal use but worth a quick check.

- **pdfplumber vs PyMuPDF on current versions:** pdfplumber is the recommended choice for license simplicity, but if scan accuracy on complex Danish PDFs proves insufficient during Phase 2 testing, PyMuPDF is the upgrade path. Evaluate empirically.

- **Python 3.11 vs 3.12 for PyInstaller:** 3.11 is the safest target as of Aug 2025. Verify current PyInstaller 6.x compatibility matrix before starting Phase 4.

---

## Sources

### Primary (HIGH confidence)
- pystray documentation and source — Win32 main-thread requirement, menu/icon API
- Python stdlib documentation — `queue.Queue` thread safety, tkinter threading constraints, `re` module
- python-docx, openpyxl, pdfplumber official documentation — API and known exception types
- PyInstaller 6.x documentation — hidden imports, spec file, onedir vs onefile tradeoffs
- Windows NTFS file locking behavior — well-established OS-level behavior
- Danish Windows encoding patterns — CP1252/UTF-8-BOM behavior on Windows Excel CSV exports

### Secondary (MEDIUM confidence)
- Training knowledge: CPR-kontoret post-2007 modulus-11 rule abandonment — well-known in Danish developer communities; official source verification recommended
- Training knowledge: pystray WM_TASKBARCREATED handling — varies by version; verify against changelog
- Training knowledge: pdfplumber memory characteristics on image-heavy PDFs — performance profile from known pdfminer behavior

### Tertiary (training knowledge, verify before relying on)
- pystray 0.19.5 as "current stable" — verify with `pip index versions pystray`
- PyInstaller 6.x hidden imports list for pdfminer — starting point only; test on clean VM

---

*Research completed: 2026-04-01*
*Ready for roadmap: yes*
