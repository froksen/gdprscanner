---
phase: 01-core-scaffolding
plan: "03"
subsystem: config-dialog
tags: [tkinter, config, ui, dialog, tabs]
dependency_graph:
  requires: ["01-02"]
  provides: ["config-dialog", "ConfigDialog"]
  affects: ["src/ui_thread.py"]
tech_stack:
  added: []
  patterns: ["tk.Toplevel for dialogs", "ttk.Notebook 3-tab layout", "ConfigStore.get_config on open / save on close"]
key_files:
  created:
    - src/config_dialog.py
  modified:
    - src/ui_thread.py
decisions:
  - "ConfigDialog uses tk.Toplevel(root) per D-06 — not a new tk.Tk root"
  - "Gem og luk saves atomically via ConfigStore.save(); X button discards changes"
  - "UIThread._config_dialog tracks instance to prevent duplicate dialog windows"
  - "_config_dialog renamed from config_dialog (private convention) to match plan spec"
metrics:
  duration: "~5 minutes"
  completed_date: "2026-04-02"
  tasks_completed: 3
  files_changed: 2
requirements_addressed: [CONF-01, CONF-02, CONF-03, CONF-04, CONF-05]
---

# Phase 1 Plan 3: Config Dialog Summary

## One-liner

3-tab tkinter config dialog (Mapper/Regler/Scanning) with folder listbox, age spinbox, file type checkboxes, frequency combobox, and atomic config persistence.

## What Was Built

### src/config_dialog.py (new, 258 lines)

`ConfigDialog` class opens as `tk.Toplevel` child of the hidden root. Three tabs built via `ttk.Notebook`:

- **Tab 0 — Mapper:** `tk.Listbox` (single-select, height=8) with vertical scrollbar. "Tilføj mappe" opens `filedialog.askdirectory` with silent deduplication. "Fjern valgt" is `state="disabled"` until `<<ListboxSelect>>` fires.
- **Tab 1 — Regler:** `ttk.Spinbox` (from=1, to=3650) for file age threshold; 7 `ttk.Checkbutton` widgets in a 3-column grid for file type extensions.
- **Tab 2 — Scanning:** `ttk.Combobox` (readonly, width=20) with 4 preset frequency options mapping to minutes (360/1440/10080/0).

Footer has right-aligned "Gem og luk" button outside the Notebook. "Gem og luk" reads all widget values, constructs config dict, calls `ConfigStore.save()`, and destroys the dialog. X button calls `_on_close` which destroys without saving.

Module-level `FREQUENCY_OPTIONS`, `FREQ_DISPLAY_TO_MINUTES`, and `FREQ_MINUTES_TO_DISPLAY` provide bidirectional display-string/minutes lookup per D-11.

### src/ui_thread.py (modified)

- Added `from src.config_dialog import ConfigDialog` import
- Replaced stub `_open_config_dialog` with full implementation:
  - Lifts and focuses existing dialog if `_config_dialog` is not None and still alive
  - Catches `tk.TclError` to detect destroyed dialogs and re-create
  - Creates `ConfigDialog(self.root, self.config_store)` on tkinter thread
- Renamed `config_dialog` attribute to `_config_dialog` (private convention)

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| Task 1 | 8bde1b5 | feat(01-03): create 3-tab ConfigDialog (Mapper, Regler, Scanning) |
| Task 2 | 5474bbc | feat(01-03): wire ConfigDialog into UIThread._open_config_dialog |
| Task 3 | (human-verify) | Human verified full application end-to-end |

## Verification

Pre-flight import check passed — all src/*.py modules import without error.

Human verification complete (Task 3): full application start confirmed, tray icon visible, config dialog opens from tray menu, settings save and persist across restart, clean shutdown verified.

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None — all widget values are read from ConfigStore on open and written back on "Gem og luk". No hardcoded empty values flow to the UI.

## Self-Check: PASSED

- src/config_dialog.py exists: FOUND
- src/ui_thread.py modified: FOUND
- Commit 8bde1b5: FOUND
- Commit 5474bbc: FOUND
