# Architecture Patterns

**Domain:** Python Windows system tray app with background file scanning
**Researched:** 2026-04-01
**Confidence:** HIGH (stable Python stdlib + pystray patterns, no external search needed)

---

## Recommended Architecture

### The Core Constraint That Drives Everything

`pystray` runs its own event loop (blocking). `tkinter` requires its mainloop on the main thread. These two loops cannot share the main thread. The standard solution is:

- **Main thread:** pystray icon loop (it must own the main thread on Windows)
- **Worker thread:** tkinter mainloop (Toplevel windows, config dialog, alert dialog)
- **Scanner thread(s):** background file scanning
- **Queue:** the single communication channel between all components

This is not an optional design decision — it is forced by the libraries.

---

## Component Map

```
┌─────────────────────────────────────────────────────────────────┐
│  Main Thread                                                     │
│  pystray.Icon (owns OS tray slot, menu, left-click)             │
│  - Callbacks run in pystray's thread                             │
│  - Dispatches to UI thread via queue                             │
└────────────────────────┬────────────────────────────────────────┘
                         │ queue.Queue (thread-safe)
         ┌───────────────┼───────────────┐
         ▼               ▼               ▼
┌────────────────┐  ┌──────────────┐  ┌──────────────────────────┐
│  UI Thread     │  │ Config Store │  │  Scanner Thread           │
│  tkinter loop  │  │ (JSON files) │  │  Scheduler + Pipeline     │
│  ConfigDialog  │  │  config.json │  │  - filter_files()         │
│  AlertDialog   │  │  ignore.json │  │  - read_content()         │
└────────┬───────┘  └──────┬───────┘  │  - scan_for_pii()        │
         │                 │           │  - emit findings          │
         │         read/write          └──────────────────────────┘
         │         on demand                        │
         │                                          │ queue.put(Finding)
         └──────────────────────────────────────────┘
                    UI thread polls queue
```

---

## Component Boundaries

| Component | Responsibility | Owns | Does NOT touch |
|-----------|---------------|------|----------------|
| `TrayApp` | OS tray icon, menu, entry point | pystray.Icon, menu callbacks | tkinter, file I/O |
| `UIThread` | All tkinter windows, dialog lifecycle | tk.Tk root, dialog open/close | scanning logic, file I/O |
| `ScanScheduler` | Periodic scan triggering, interval config | threading.Timer or sleep loop | UI, config writes |
| `ScanPipeline` | File filtering, reading, PII detection | file handles, regex | UI, config, scheduling |
| `ConfigStore` | Read/write JSON config and ignore list | config.json, ignore.json | UI rendering, scanning |
| `FindingQueue` | Typed events between scanner and UI | queue.Queue instance | business logic |

---

## Data Flow

### Scan Cycle (happy path)

```
ScanScheduler.tick()
  → ScanPipeline.run(folders, age_limit, file_types)
      → filter_files()    — os.walk + mtime check + extension filter
      → [for each file]
          → read_content() — docx/xlsx/csv/pdf/txt extraction
          → scan_for_pii() — regex CPR, email, phone + header heuristics
          → if hit: FindingQueue.put(Finding(path, reasons, snippet))
  → UIThread polls queue
      → AlertDialog.show(Finding)
          → user chooses: Delete / Keep / Ignore
              → Delete: os.remove(path), close dialog
              → Keep:   close dialog, no action
              → Ignore: ConfigStore.add_to_ignore(path), close dialog
```

### Config Change Flow

```
User opens config from tray menu
  → TrayApp callback → FindingQueue.put(OpenConfigEvent)
  → UIThread receives event → ConfigDialog.show()
      → on save: ConfigStore.write(config.json)
      → ScanScheduler notified (re-reads config on next tick)
```

### Startup Flow

```
main()
  → ConfigStore.load()           — read config.json + ignore.json
  → UIThread.start()             — daemon thread with tk.Tk()
  → ScanScheduler.start()        — daemon thread
  → TrayApp.run()                — BLOCKS main thread (pystray requirement)
```

---

## Thread Model: Why Not asyncio, Why Not multiprocessing

**asyncio:** File I/O in Python is not truly async without an executor. The scanning loop is CPU + I/O bound (regex over file contents). asyncio adds complexity with no benefit for a single-user local tool. Rejected.

**multiprocessing:** Process startup overhead (~500ms per scan cycle), IPC complexity (pipes/shared memory), no meaningful benefit for single-user local scanning of local files. Memory isolation is a cost not a benefit here. Rejected.

**threading with queue.Queue:** Simple, well-understood, low overhead. GIL is not a bottleneck here — the scanner spends most time in I/O (file reads) and C-extension regex, both of which release the GIL. The queue provides safe, decoupled communication. Chosen.

**Recommended threading layout:**

```python
threads = {
    "main":      "pystray icon loop (required by pystray on Windows)",
    "ui":        "tkinter mainloop — one persistent daemon thread",
    "scanner":   "single scanner thread — sequential scan cycles",
}
```

A single scanner thread (not a pool) is correct here: scanning is I/O bound and the user does not need parallelism — they need low resource usage and predictable behavior.

---

## The FindingQueue: Central Nervous System

Use a single `queue.Queue` for all cross-thread events. Define typed events as dataclasses:

```python
@dataclass
class FindingEvent:
    type: Literal["finding"] = "finding"
    path: str = ""
    reasons: list[str] = field(default_factory=list)
    snippet: str = ""

@dataclass
class OpenConfigEvent:
    type: Literal["open_config"] = "open_config"

@dataclass
class ShutdownEvent:
    type: Literal["shutdown"] = "shutdown"
```

The UI thread runs `queue.get(timeout=0.1)` in a polling loop (tkinter `after()` callback), not a blocking `get()`. This keeps the tkinter mainloop alive and responsive.

```python
def _poll_queue(self):
    try:
        event = self.queue.get_nowait()
        self._handle_event(event)
    except queue.Empty:
        pass
    self.root.after(100, self._poll_queue)  # reschedule every 100ms
```

This is the correct pattern — do NOT call `queue.get()` blocking from the tkinter thread.

---

## Scan Pipeline: Internal Structure

The pipeline inside `ScanPipeline` should be structured as discrete, testable stages:

```
Stage 1 — filter_files(folders, age_days, extensions, ignore_list) → [Path]
  Input:  config parameters + ignore list
  Output: list of candidate file paths
  Logic:  os.walk, stat().st_mtime, suffix filter, ignore set lookup

Stage 2 — read_content(path) -> str | None
  Input:  single file path
  Output: extracted text or None on error
  Logic:  dispatch by extension to extractor:
          .txt/.log/.csv  → open(encoding errors='ignore')
          .docx           → python-docx paragraph join
          .xlsx/.xls      → openpyxl / xlrd cell values
          .pdf            → pdfplumber or PyMuPDF page text

Stage 3 — scan_for_pii(text, filename) -> list[Finding]
  Input:  extracted text + filename
  Output: list of reason strings + snippets
  Logic:  Layer 1: filename pattern match (CPR, kunde, patient, ...)
          Layer 2: regex scan of text content:
                   CPR  — \b\d{6}[-]?\d{4}\b with Luhn-style modulus-11 check
                   email — standard RFC-ish pattern
                   phone — Danish: \b(\+45|0045)?[ ]?\d{8}\b
          Layer 3: header heuristics — first row/column labels in CSV/XLSX

Stage 4 — emit(finding) → queue.put(FindingEvent)
  Input:  Finding from stage 3
  Output: event on queue (no return value)
```

Each stage is a pure function (or near-pure). This makes unit testing each stage trivial without spinning up the full application.

---

## Alert Dialog: Modality and Sequencing

The alert dialog must handle the case where multiple findings arrive before the user acts. Two valid approaches:

**Option A — Queue-gated (recommended):** Only show one dialog at a time. When dialog is open, do not dequeue the next finding until current dialog is closed. The scanner continues and findings accumulate in the queue. User processes them one by one after the scan completes.

**Option B — Notification + batch review:** Show a tray notification bubble ("3 GDPR files found"), open a list dialog when user clicks. More complex, deferred to later milestone if needed.

Use Option A for the initial build. It maps directly to the queue-polling architecture with minimal state.

The alert dialog is a `tk.Toplevel` (not a new `tk.Tk()`). One `tk.Tk()` root per process — additional windows are `Toplevel`.

---

## Config Store: Persistence Pattern

Two JSON files, both in a single app data directory:

```
%APPDATA%\GDPRScanner\
    config.json       — scan settings (folders, age_limit, interval, file_types)
    ignore.json       — list of absolute file paths to ignore
```

`ConfigStore` is a simple class with `load()`, `save()`, `add_to_ignore()`, `is_ignored()`. It is NOT a singleton — pass the instance explicitly to components that need it. This avoids hidden global state and makes testing easier.

The ignore list is a Python `set` in memory (fast O(1) lookup during scan) backed by a JSON array on disk. Load once at startup, write after each ignore action.

---

## Scalability / Resource Budget

| Concern | Approach |
|---------|----------|
| Large folder trees (100K+ files) | Stage 1 filter runs fast (stat only, no open). Yield from os.walk, do not collect all paths upfront. |
| Large files (multi-MB PDFs/XLSX) | Read in chunks or page-by-page. Cap extraction at first N KB (e.g., 512 KB) per file — GDPR data is typically in headers/early rows. |
| Scan blocking UI | Scanner is on its own thread. UI remains responsive. Tray menu gets a "Scanning..." state indicator via queue event. |
| Frequent scans hammering disk | Minimum interval enforced in ScanScheduler (e.g., 15 min floor). User-configurable above that. |
| Memory | Text extraction is ephemeral — extract, scan, discard. Do not accumulate all extracted text. |

---

## Suggested Build Order (Component Dependencies)

```
1. ConfigStore            — no dependencies, used by everything
2. ScanPipeline stages    — depends only on ConfigStore (for ignore list)
   a. filter_files()
   b. read_content() extractors (one file type at a time)
   c. scan_for_pii() detectors (one pattern at a time)
3. FindingQueue + events  — pure dataclasses, no dependencies
4. UIThread skeleton      — tk.Tk loop + queue polling, no dialogs yet
5. AlertDialog            — depends on UIThread + FindingQueue
6. ConfigDialog           — depends on UIThread + ConfigStore
7. TrayApp                — depends on all of the above
8. ScanScheduler          — depends on ScanPipeline + FindingQueue
9. main() wiring          — assembles all components, starts threads
```

Build order rationale: Each numbered item only depends on items built before it. ConfigStore first means every subsequent component can be tested with real config. ScanPipeline stages built independently mean PII detection is testable before any UI exists. UIThread skeleton before dialogs means the polling loop is proven before adding dialog complexity.

---

## Anti-Patterns to Avoid

### Calling tkinter from the scanner thread
**What goes wrong:** `tk.Label()`, `messagebox.showwarning()`, or any tkinter call from outside the UI thread causes random crashes or silent failures on Windows.
**Prevention:** All tkinter calls go through the queue. The UI thread is the only thread that touches tkinter objects.

### Blocking queue.get() inside tkinter after() callback
**What goes wrong:** `queue.get(block=True)` inside an `after()` callback blocks the tkinter mainloop, freezing the UI.
**Prevention:** Always use `queue.get_nowait()` with a try/except Empty inside the polling callback.

### Running pystray in a non-main thread on Windows
**What goes wrong:** pystray on Windows uses win32 message pump internals that require the main thread. Running it in a daemon thread causes the icon to not appear or crash silently.
**Prevention:** pystray.Icon.run() must be called from the main thread. This is the constraint that pushes tkinter to a worker thread.

### Global mutable state for config
**What goes wrong:** Scanner thread reads config while UI thread writes it — race condition.
**Prevention:** ConfigStore.save() and ConfigStore.load() are called only from the UI thread or under a threading.Lock(). The scanner reads a snapshot at the start of each scan cycle, not live config.

### One tk.Tk() per dialog
**What goes wrong:** Multiple `tk.Tk()` instances causes event loop conflicts and broken widget styles.
**Prevention:** One `tk.Tk()` root, all dialogs are `tk.Toplevel(root)`.

---

## Sources

- pystray documentation and source (stable API, Windows COM/win32 main thread requirement is documented behavior)
- Python threading documentation — queue.Queue thread safety guarantees
- tkinter threading constraints — documented in Python docs: "tkinter is not thread-safe; all calls must be from the main thread" (adapted here: UI thread owns all tk calls)
- Pattern confidence: HIGH — these are well-established constraints of these specific libraries, not speculative
