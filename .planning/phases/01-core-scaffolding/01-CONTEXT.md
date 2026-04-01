# Phase 1: Core Scaffolding - Context

**Gathered:** 2026-04-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Establish the foundational architecture: pystray tray icon running on the main thread, tkinter config dialog running on a worker thread, cross-thread communication via queue.Queue, config persistence to %APPDATA%\GDPRScanner\config.json, and a scheduler skeleton that fires at configured intervals. No scanning logic — only the infrastructure that Phase 2 will plug into.

</domain>

<decisions>
## Implementation Decisions

### Threading architecture
- **D-01:** pystray owns the main thread (required by Win32 message pump — this is a hard constraint, not a preference)
- **D-02:** tkinter runs on a dedicated worker daemon thread
- **D-03:** All cross-thread communication uses a single `queue.Queue` with typed dataclass events (e.g., `OpenConfigEvent`, `ScanNowEvent`, `ShutdownEvent`)
- **D-04:** The tkinter worker polls the queue with `root.after(100, ...)` — never blocking `queue.get()`

### Config dialog struktur
- **D-05:** Three-tab layout: **Mapper** | **Regler** | **Scanning**
  - *Mapper*: Add/remove scan folders
  - *Regler*: File age threshold (days), file type checkboxes (.docx, .xlsx, .xls, .csv, .pdf, .txt, .log)
  - *Scanning*: Scan frequency dropdown
- **D-06:** Dialog is a `tk.Toplevel` (not a new `tk.Tk()` root — only one Tk root per process)
- **D-07:** "Gem og luk" button saves to config.json and destroys the Toplevel

### Mappevalg UI
- **D-08:** Listbox showing currently configured folders, with two buttons below: "Tilføj mappe" (opens `filedialog.askdirectory`) and "Fjern valgt" (removes selected entry)
- **D-09:** Listbox allows single-selection for removal; multiple folders can be added one at a time

### Scanningsfrekvens
- **D-10:** Dropdown (`ttk.Combobox` readonly) with four preset options:
  - "Hvert 6. time" (6 hours)
  - "Dagligt" (24 hours) — **default**
  - "Ugentligt" (168 hours)
  - "Kun manuelt" (scheduler disabled; only "Scan nu" from tray triggers a scan)
- **D-11:** Frequency stored in config.json as integer minutes (e.g., `"scan_interval_minutes": 1440`)

### Tray-ikon
- **D-12:** Icon generated programmatically with Pillow — a simple shield/circle shape in blue (#2563EB) with white "G" letter, 64×64 pixels — no .ico file required
- **D-13:** pystray `Icon` object created with the Pillow `Image` object directly

### Config persistence
- **D-14:** Config file path: `os.path.join(os.environ["APPDATA"], "GDPRScanner", "config.json")`
- **D-15:** `%APPDATA%\GDPRScanner\` directory created on first run if it does not exist
- **D-16:** Config written atomically (write to temp file, rename) to prevent corruption on crash
- **D-17:** Default config created on first launch if no config.json exists:
  ```json
  {
    "scan_folders": [],
    "file_age_days": 30,
    "scan_interval_minutes": 1440,
    "file_types": [".docx", ".xlsx", ".xls", ".csv", ".pdf", ".txt", ".log"]
  }
  ```

### Scheduler skeleton
- **D-18:** `ScanScheduler` runs on a separate daemon thread; uses `threading.Event` with a timeout loop rather than `time.sleep` so it can be interrupted cleanly on shutdown
- **D-19:** "Scan nu" from the tray menu posts a `ScanNowEvent` to the queue — Phase 2 will consume this; in Phase 1 it just logs "Scan triggered"
- **D-20:** Scheduler respects "Kun manuelt" by disabling its timed loop entirely

### Claude's Discretion
- Exact font sizes and padding in the config dialog
- Whether to show a tooltip on the tray icon
- Handling of duplicate folder entries in the listbox (silently deduplicate is fine)
- Whether "Fjern valgt" is disabled when no item is selected, or raises an error

</decisions>

<specifics>
## Specific Ideas

- Tray menu items in Danish: "Åbn indstillinger", "Scan nu", "Afslut" (exact strings from ROADMAP.md success criteria)
- The config dialog should open quickly — no heavy initialization; all settings loaded from config.json at dialog open time
- File type checkboxes use the exact extensions from the default config list above

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project requirements and architecture
- `.planning/REQUIREMENTS.md` — TRAY-01..04, CONF-01..06, SCHED-01..03 (the phase's acceptance criteria)
- `.planning/ROADMAP.md` §Phase 1 — Success criteria (exact tray menu strings, config.json path)
- `.planning/research/ARCHITECTURE.md` — Threading model, component boundaries, anti-patterns
- `.planning/research/STACK.md` — Library versions, pystray constraints, tkinter threading notes
- `.planning/research/PITFALLS.md` — pystray main-thread pitfall, tkinter thread safety, config atomicity

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- None — greenfield project, no existing code

### Established Patterns
- None yet — this phase establishes the patterns that subsequent phases will follow

### Integration Points
- Phase 2 (Scan Pipeline) will add a `ScanEngine` that receives `ScanNowEvent` from the queue and emits `FindingEvent` back
- Phase 3 (Alert Dialog) will add a `FindingDialog` as another `tk.Toplevel` on the same tkinter worker thread

</code_context>

<deferred>
## Deferred Ideas

- None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-core-scaffolding*
*Context gathered: 2026-04-01*
