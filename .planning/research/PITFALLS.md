# Domain Pitfalls

**Domain:** Python Windows system tray app with background file scanning (GDPR detector)
**Researched:** 2026-04-01
**Confidence notes:** Training data (cutoff Aug 2025). WebSearch and WebFetch unavailable. All pitfalls below are HIGH/MEDIUM confidence from well-established Python ecosystem patterns. CPR checksum specifics are MEDIUM confidence — verify against official Danish CPR authority documentation.

---

## Critical Pitfalls

Mistakes that cause rewrites, silent data corruption, or persistent crashes.

---

### Pitfall 1: pystray Must Own the Main Thread on Windows

**What goes wrong:** You call `icon.run()` from a background thread while tkinter runs on the main thread. On Windows the system tray backend (`pystray` uses `win32api`/`win32con` under the hood) requires a Win32 message pump on the thread that created the icon. Running it off-thread produces a tray that appears but whose menu callbacks silently fail, the icon vanishes after sleep/wake, or the process hangs on exit.

**Why it happens:** Win32 UI objects have thread affinity. Python developers assume GUI = main thread but put tkinter there and shunt pystray off.

**Consequences:** Menu clicks do nothing, icon disappears randomly, clean shutdown is impossible.

**Prevention:**
- Run `icon.run()` on the **main thread**.
- Drive tkinter from a daemon thread using `root.after()` for all UI updates, or open tkinter windows only in response to menu callbacks (which pystray invokes on a worker thread — so you must use `threading.Thread` + `root.after(0, ...)` to schedule into the tkinter main loop from there).
- Never call tkinter widget methods directly from pystray callbacks; always marshal back via `root.after()`.

**Warning signs:** Menu items registered but clicking them does nothing. No exception raised.

**Phase:** Core scaffolding / Phase 1.

---

### Pitfall 2: tkinter `mainloop()` Blocks — You Cannot Call It Twice

**What goes wrong:** Opening a config dialog with `Toplevel()` or calling `mainloop()` a second time from a pystray callback causes a deadlock or "main thread is not in main loop" RuntimeError on Windows.

**Why it happens:** tkinter on Windows must have exactly one `mainloop()` call on one thread. pystray callbacks come in on worker threads; any direct tkinter construction there raises errors.

**Consequences:** App hard-crashes or becomes unresponsive when the user opens the config dialog.

**Prevention:**
- Use `root.after(0, open_dialog_func)` to schedule dialog creation back onto the tkinter thread.
- Keep a single persistent hidden `Tk()` root that never closes (use `root.withdraw()` to hide it). All dialogs are `Toplevel` children of that root.
- Never destroy the root `Tk` instance — use `withdraw()` instead.

**Warning signs:** Works on first open, crashes or hangs on second open. `RuntimeError: main thread is not in main loop`.

**Phase:** Core scaffolding / Phase 1.

---

### Pitfall 3: Scanner Thread Reading Files Held Open by Another Process (Windows File Locking)

**What goes wrong:** On Windows, Office applications (Word, Excel) open `.docx`/`.xlsx` files with an exclusive or shared lock. Attempting to open these files for reading raises `PermissionError` or returns a corrupt byte stream. The scanner crashes or logs an exception and skips the file silently.

**Why it happens:** Windows file locking is mandatory (not advisory like POSIX). A file open in Word is byte-locked.

**Consequences:** Files that are most likely to contain live personal data (currently open spreadsheets) are exactly the ones silently skipped.

**Prevention:**
- Wrap every file open in `try/except (PermissionError, OSError)` and skip gracefully.
- Log skipped-due-to-lock files to a "retry queue" and re-attempt on next scan cycle.
- Do NOT attempt to copy the file to a temp location to bypass the lock — this can produce partial/corrupt reads and is racy.
- For `.docx`/`.xlsx`, the file is a ZIP archive internally; `zipfile.ZipFile` raises `BadZipFile` on partial reads — catch that too.

**Warning signs:** `PermissionError: [WinError 32] The process cannot access the file because it is being used by another process`.

**Phase:** Content scanning / Phase 2.

---

### Pitfall 4: python-docx / openpyxl Raise Unhandled Exceptions on Malformed Files

**What goes wrong:** Real-world `.docx` and `.xlsx` files are often created by non-Microsoft tools (LibreOffice, Google Docs exports, old macros), contain embedded objects, or are password-protected. `python-docx` raises `BadZipFile`, `KeyError`, `lxml.etree.XMLSyntaxError`, or `PackageNotFoundError`. `openpyxl` raises `InvalidFileException`, `KeyError` on missing sheets, or hangs indefinitely on very large files with many formula cells.

**Why it happens:** Both libraries assume well-formed OOXML. Real files are not always well-formed.

**Consequences:** One bad file in a directory crashes the entire scan run if exceptions are not caught per-file.

**Prevention:**
- Wrap each file parse in a broad `try/except Exception` per file, log the filename + error, and continue.
- For `.docx`: catch `BadZipFile` (from `zipfile`), `KeyError`, `PackageNotFoundError` (from `docx`).
- For `.xlsx`: catch `InvalidFileException`, `BadZipFile`, `KeyError`. Set `read_only=True` and `data_only=True` in `openpyxl.load_workbook()` — this avoids loading formula engine and dramatically reduces memory on large files.
- For password-protected files: `python-docx` raises `BadZipFile` immediately. Detect and skip.
- Add a file-size guard: skip files over a configurable threshold (e.g., 50 MB) before attempting to parse.

**Warning signs:** Scan terminates early. One file kills the whole run.

**Phase:** Content scanning / Phase 2.

---

### Pitfall 5: pdfplumber Memory Exhaustion on Large PDFs

**What goes wrong:** `pdfplumber` (built on `pdfminer.six`) loads the full PDF structure into memory for text extraction. A 200-page scanned PDF with embedded images can consume 500 MB–1 GB of RAM and block the scanner thread for 30–120 seconds. On a background daemon this causes system-wide memory pressure and apparent freezes.

**Why it happens:** pdfminer parses the entire object graph. Image-heavy PDFs with little text still incur the full parse cost.

**Consequences:** Background scanner makes the machine sluggish. User notices and kills the process.

**Prevention:**
- Set a file-size guard before opening any PDF (e.g., skip files > 20–30 MB unless the user explicitly opts in).
- Use `pdfplumber.open()` as a context manager and extract page-by-page with early exit once enough evidence is found.
- Set a page count limit (e.g., first 10 pages only) for initial scanning; flag for deeper scan on match.
- Consider `pymupdf` (fitz) as an alternative — it is significantly faster and lower-memory for text extraction, though it adds a larger binary dependency.
- Run PDF parsing in a subprocess with a timeout to prevent runaway parses from blocking the scanner thread indefinitely.

**Warning signs:** Machine fan spins up during scans. `psutil` shows memory climbing per PDF.

**Phase:** Content scanning / Phase 2.

---

### Pitfall 6: CPR Checksum Validation — Modulus-11 Is Not Universal

**What goes wrong:** The classic Danish CPR checksum algorithm uses modulus-11 with weights `[4, 3, 2, 7, 6, 5, 4, 3, 2, 1]`. Developers implement this and assume all valid CPR numbers pass it. However: (1) CPR numbers issued after **~2007** for people born after 1 Jan 2007 **do not conform to the modulus-11 rule** because the number space was exhausted. The Danish CPR registry officially abandoned the checksum for new issuances. (2) Numbers issued to foreign nationals ("erstatningspersoner") also do not pass the checksum.

**Why it happens:** Outdated documentation and StackOverflow answers describe the old checksum. The authoritative source (CPR-kontoret) changed the rules but internet resources lag.

**Consequences:**
- If you use checksum validation to REDUCE false positives, you will miss valid CPR numbers for people born after 2007 — a systematic blind spot for the youngest demographic.
- If you skip checksum validation, you get higher false positives (any 10-digit string matching `DDMMYY-XXXX` format passes).

**Prevention:**
- Do NOT use modulus-11 as the sole validity gate. Use it as a confidence booster, not a filter.
- Validate the date portion (`DD`, `MM`, `YY`) as a real calendar date — this eliminates most random number matches without the checksum problem.
- Validate the 7th digit (century indicator: 0–3 = 1900s, 4–9 = context-dependent for 2000s) to further reduce false positives.
- Recommended logic: `valid_date(DD, MM, YY) AND (passes_mod11 OR born_after_2007_heuristic)`. When in strict mode, require valid date + plausible century digit, but do NOT require mod-11.

**Warning signs:** Testing with CPR numbers of people born 2007+ finds no matches even though the regex matches the format.

**Phase:** Detection engine / Phase 2.

**Confidence:** MEDIUM — the mod-11 abandonment is documented in Danish government sources and well-known in Danish developer communities, but the exact cutoff year and exact rule for the 7th digit century code should be verified against current CPR-kontoret documentation before shipping.

---

### Pitfall 7: Regex False Positives for CPR — Phone Numbers and Account Numbers Match the Pattern

**What goes wrong:** The CPR format `DDMMYY-XXXX` or without separator `DDMMYYXXXX` matches many innocent 10-digit sequences: bank account numbers, phone numbers in international format, invoice numbers, ZIP+4 codes in spreadsheets. A naive regex `\b\d{6}[-\s]?\d{4}\b` will fire on columns of phone numbers, order IDs, and customer numbers.

**Why it happens:** 10-digit numeric strings are extremely common in business documents. The CPR pattern has no structurally unique delimiter.

**Consequences:** High false positive rate causes alert fatigue. User starts ignoring warnings — defeating the entire product.

**Prevention:**
- Always validate the date component: `DD` in 01–31, `MM` in 01–12. Eliminates most random number matches.
- Require that the match is NOT immediately preceded or followed by more digits (true word boundary, not just `\b` which fails at `-`).
- Consider context: if the surrounding text contains words like "telefon", "tlf", "tel", "ordre", "faktura", "konto" within 50 characters, downgrade confidence or skip.
- In column-oriented files (CSV, Excel), if a column header contains "cpr" or "personnummer", elevate confidence for all values in that column. If the header is "telefon" or "ordre", suppress CPR detection for that column.
- Do not fire on values where more than 50% of rows in the same column match the same pattern (i.e., it is clearly a systematic ID field, not a CPR field).

**Warning signs:** High match counts in files you know contain no personal data.

**Phase:** Detection engine / Phase 2.

---

## Moderate Pitfalls

---

### Pitfall 8: Scanner Thread Starves I/O — No Rate Limiting or Sleep Between Files

**What goes wrong:** A tight loop that opens, reads, and closes every matching file as fast as possible will peg disk I/O at 100% on spinning HDDs or thermal-throttle NVMe drives. On Windows this causes Explorer to become sluggish and other applications to stall during the scan.

**Prevention:**
- Insert a small `time.sleep(0.01–0.05)` between file operations in the scanner loop, or use a configurable inter-file delay.
- Honour the user-configured scan interval — do not immediately re-scan after completing a full pass.
- Use `os.scandir()` (not `os.walk()` with `os.path.getsize()` calls) — `scandir()` retrieves size and mtime from the directory entry in one syscall rather than a separate `stat()` per file.
- Apply the age filter (`mtime > threshold`) before opening files — avoid reading files that will be discarded anyway.

**Warning signs:** Disk LED stays solid during scan. User reports system slowdown.

**Phase:** Scanner infrastructure / Phase 1.

---

### Pitfall 9: openpyxl Iterating All Cells Including Empty Ones

**What goes wrong:** The default `openpyxl` iteration (`ws.iter_rows()`) includes every cell in the used range, which for poorly constructed spreadsheets can be the entire sheet (1,048,576 rows × 16,384 columns). This occurs when a spreadsheet has had data pasted far from the origin, leaving phantom "used" cells.

**Prevention:**
- Use `ws.dimensions` to check used range before iterating.
- Clamp iteration to the first N rows (e.g., 1000) for initial scanning; only go deeper if matches are found.
- Use `read_only=True` mode — this streams rows rather than loading the full workbook object graph.

**Warning signs:** `openpyxl` hangs on a file that looks small on disk.

**Phase:** Content scanning / Phase 2.

---

### Pitfall 10: Config/Ignore-List JSON File Corruption on Unclean Shutdown

**What goes wrong:** If the app writes JSON config or the ignore-list while the process is killed (e.g., Windows shutdown, task manager), the file can be left as a partial write — valid JSON prefix, truncated. On next start, `json.loads()` raises `JSONDecodeError` and the app either crashes or silently loses all settings.

**Prevention:**
- Write to a `.tmp` file first, then `os.replace()` (atomic rename on Windows NTFS) to the target path.
- On startup, catch `JSONDecodeError` and fall back to defaults, logging a warning rather than raising.
- Keep a rolling backup of the previous config (`.bak`) so one bad write does not destroy history.

**Warning signs:** App starts with blank settings after a system crash.

**Phase:** Core scaffolding / Phase 1.

---

### Pitfall 11: PyInstaller Missing Hidden Imports for pystray, pdfplumber, and win32

**What goes wrong:** PyInstaller's static analysis misses dynamically imported modules. Common missing imports for this stack:
- `pystray._win32` (the Windows backend — pystray selects backend at runtime)
- `PIL.Image` and `PIL.ImageDraw` (pystray requires Pillow for the icon; often not detected)
- `pdfminer` submodules (pdfplumber delegates to pdfminer which uses late imports)
- `win32api`, `win32con`, `pywintypes` (pywin32 uses late binding)
- `pkg_resources` / `importlib.metadata` (used by several libraries for version detection)

**Consequences:** Packaged `.exe` crashes at runtime with `ModuleNotFoundError` even though it works fine from the source environment.

**Prevention:**
- Maintain a `gdprscanner.spec` file (not `--onefile` for development — use `--onedir` first to inspect what is included).
- Add `hiddenimports=['pystray._win32', 'PIL', 'PIL.Image', 'PIL.ImageDraw', 'pdfminer.high_level', 'pdfminer.layout', 'win32api', 'win32con', 'win32gui', 'pywintypes']` to the spec.
- Use `--collect-all pdfplumber` and `--collect-all pdfminer` in the spec.
- Test the packaged build on a clean VM (no Python installed) before releasing.
- Set `console=False` in the spec to avoid a spurious console window, but keep a log file to capture startup errors.

**Warning signs:** Works from `python main.py`, crashes from `.exe`. `ModuleNotFoundError` in the log.

**Phase:** Packaging / Phase 3 (or final milestone).

---

### Pitfall 12: pystray Icon Disappears After Windows Explorer Restart

**What goes wrong:** When Windows Explorer (the shell) crashes and restarts (common after Windows updates, or user-triggered `explorer.exe` restart), all system tray icons from running applications are removed. Most applications re-register by listening for the `WM_TASKBARCREATED` message. `pystray` does NOT handle this automatically in all versions.

**Prevention:**
- Check pystray's current version changelog — versions after ~0.19 may handle this. If not, register a win32 window procedure that listens for `WM_TASKBARCREATED` (registered via `RegisterWindowMessage`) and calls `icon.update_menu()` or re-runs the icon setup.
- As a workaround: include a "Restart tray icon" menu item that re-calls the icon setup.
- This is a LOW-priority edge case for personal use, but worth noting.

**Warning signs:** After `taskkill /f /im explorer.exe && explorer.exe`, the tray icon is gone but the process is still running.

**Phase:** Polish / Phase 3.

**Confidence:** MEDIUM — pystray's handling of `WM_TASKBARCREATED` varies by version; verify against pystray changelog.

---

### Pitfall 13: CSV Encoding Detection — Windows-1252 vs UTF-8 vs UTF-8-BOM

**What goes wrong:** CSV files on Danish Windows systems are commonly saved in Windows-1252 (Latin-1 superset) by Excel, not UTF-8. Opening with `open(path, encoding='utf-8')` raises `UnicodeDecodeError` on any file containing Danish characters (æ, ø, å). Conversely, some files have a UTF-8 BOM (`\xef\xbb\xbf`) that confuses naive parsers.

**Prevention:**
- Use `encoding='utf-8-sig'` as the first attempt (handles UTF-8 with and without BOM).
- Fall back to `encoding='cp1252'` on `UnicodeDecodeError`.
- Final fallback: `encoding='latin-1'` which never raises (it maps every byte to a Unicode code point).
- Do NOT use `chardet` for automatic detection in a tight loop — it reads the entire file to guess encoding, doubling I/O cost. Use the fallback chain instead.

**Warning signs:** `UnicodeDecodeError: 'utf-8' codec can't decode byte 0xe6` (0xe6 = 'æ' in cp1252).

**Phase:** Content scanning / Phase 2.

---

## Minor Pitfalls

---

### Pitfall 14: `os.walk()` Follows Symlinks and Junction Points

**What goes wrong:** Windows NTFS junction points and symlinks can create loops. `os.walk(followlinks=False)` (the default) is safe, but developers sometimes explicitly set `followlinks=True` for convenience. A junction loop will cause infinite scanning.

**Prevention:**
- Never set `followlinks=True`. Use the default.
- Add a `max_depth` guard in the walk loop as a safety net.

**Phase:** Scanner infrastructure / Phase 1.

---

### Pitfall 15: `.doc` Files (Old Binary Word Format) Are Not Readable by python-docx

**What goes wrong:** `python-docx` only reads `.docx` (OOXML). Attempting to open a `.doc` (binary OLE compound format) raises `BadZipFile` immediately. Old `.doc` files are common in business environments.

**Prevention:**
- Detect `.doc` by extension and handle separately.
- Options: (a) skip `.doc` files with a log note, (b) use `python-oletools` (`oletools.olevba`) which can extract some text from `.doc`, (c) invoke LibreOffice headlessly to convert — too heavy for this use case.
- Recommended: skip `.doc` in v1, document the limitation. Add `python-oletools` support in a later phase if users request it.

**Phase:** Content scanning / Phase 2.

---

### Pitfall 16: tray `stop()` Does Not Join Background Threads

**What goes wrong:** Calling `icon.stop()` terminates pystray's event loop but does not stop the scanner thread. If the scanner thread holds a file open or is mid-write to the config JSON, the process may hang or corrupt data on exit.

**Prevention:**
- Use a `threading.Event` (`shutdown_event`) that the scanner thread checks between file operations.
- In the "Quit" menu callback: set the event, call `icon.stop()`, then join the scanner thread with a timeout before `sys.exit(0)`.

**Phase:** Core scaffolding / Phase 1.

---

### Pitfall 17: Windows Defender / Antivirus Flags PyInstaller Executables

**What goes wrong:** PyInstaller-packaged executables have a well-known pattern that causes Windows Defender and other AV tools to flag them as potentially malicious (the self-extracting stub is similar to malware packers). This is especially common with `--onefile` mode.

**Prevention:**
- Prefer `--onedir` (folder distribution) over `--onefile` — the individual files are less likely to be flagged.
- For personal use this is less critical, but document it in release notes.
- Consider signing the executable with a code-signing certificate if distributing to others.

**Phase:** Packaging / Phase 3.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Core scaffolding (tray + tkinter wiring) | pystray must own main thread; tkinter callbacks from wrong thread | pystray on main thread; marshal all tkinter calls via `root.after()` |
| Core scaffolding (config persistence) | JSON corruption on unclean shutdown | Atomic write via temp file + `os.replace()` |
| Scanner infrastructure (file walk) | I/O starvation; symlink loops; unnecessary stat() calls | Sleep between files; `os.scandir()`; no `followlinks` |
| Content scanning (.docx/.xlsx) | Malformed files crash scan; large files exhaust memory | Per-file try/except; `read_only=True`; file-size guard |
| Content scanning (.pdf) | Memory exhaustion; blocking scan thread | Size guard; page limit; page-by-page iteration |
| Content scanning (.csv) | Encoding errors on Danish characters | utf-8-sig → cp1252 → latin-1 fallback chain |
| Detection engine (CPR) | Mod-11 filters valid post-2007 CPR numbers | Date validation + century digit; mod-11 as booster not filter |
| Detection engine (false positives) | Phone/account numbers match CPR pattern | Column-header context; date validation; neighbour-text suppression |
| Packaging (PyInstaller) | Missing hidden imports; AV flags | Explicit hiddenimports in spec; --onedir; test on clean VM |
| Shutdown | Scanner thread not joined on exit | shutdown_event + thread.join() before sys.exit() |

---

## Sources

**Confidence note:** WebSearch and WebFetch were unavailable during this research session. All findings are drawn from training data (cutoff August 2025) covering:
- pystray source code and issue tracker patterns (HIGH confidence — well-documented Win32 threading constraint)
- python-docx and openpyxl official documentation and known exception types (HIGH confidence)
- pdfplumber / pdfminer known performance characteristics (HIGH confidence)
- PyInstaller documentation on hidden imports (HIGH confidence)
- CPR modulus-11 rule change (MEDIUM confidence — verify against CPR-kontoret official documentation before shipping detection engine)
- Windows file locking behavior (HIGH confidence — fundamental OS behavior)
- Encoding patterns for Danish Windows CSV files (HIGH confidence)

**Verification recommended before Phase 2:**
- CPR-kontoret official CPR number format documentation (confirm post-2007 behavior and century digit encoding)
- pystray changelog for WM_TASKBARCREATED handling (confirm which version added support)
- pdfplumber/pymupdf performance comparison on current versions
