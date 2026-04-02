---
phase: 01-core-scaffolding
plan: 01
subsystem: data-layer
tags: [events, config, persistence, icon, pillow, pystray]
dependency_graph:
  requires: []
  provides: [src/events.py, src/config_store.py, src/icon.py, requirements.txt]
  affects: [all subsequent plans — events and ConfigStore are consumed by every component]
tech_stack:
  added: [Pillow>=10.0.0, pystray>=0.19.5]
  patterns: [atomic-write-via-os-replace, dataclass-typed-events, deep-copy-thread-safe-snapshot]
key_files:
  created:
    - src/__init__.py
    - src/events.py
    - src/config_store.py
    - src/icon.py
    - requirements.txt
  modified: []
decisions:
  - "ConfigStore class attributes APP_DIR and CONFIG_FILE use pathlib.Path resolved at class definition time from os.environ['APPDATA']"
  - "Atomic write uses os.replace() on a .tmp sibling file per D-16 and Pitfall 10 — no rolling .bak in Phase 1 (deferred)"
  - "Icon font falls back to ImageFont.load_default() when segoeuib.ttf unavailable; glyph centering uses textbbox offset correction"
metrics:
  duration_seconds: 89
  completed_date: "2026-04-02"
  tasks_completed: 2
  tasks_total: 2
  files_created: 5
  files_modified: 0
---

# Phase 01 Plan 01: Data Layer Foundation Summary

**One-liner:** Typed dataclass event queue protocol, atomic JSON ConfigStore with APPDATA persistence, and Pillow-generated 64x64 RGBA tray icon.

---

## What Was Built

### Task 1 — Event dataclasses and ConfigStore (commit: 78251be)

**src/events.py** defines four typed dataclasses for cross-thread queue communication:
- `OpenConfigEvent` — triggers config dialog open
- `ScanNowEvent` — triggers manual scan
- `ShutdownEvent` — signals clean shutdown
- `ScanCompleteEvent` — reports scan results (files_scanned, findings_count)

**src/config_store.py** implements `ConfigStore`:
- Creates `%APPDATA%/GDPRScanner/` on first instantiation
- Loads config.json; falls back silently to `DEFAULT_CONFIG` on `FileNotFoundError` or `json.JSONDecodeError` (Pitfall 10)
- `save()` writes atomically via temp file + `os.replace()` (D-16)
- `get_config()` returns `copy.deepcopy()` snapshot for thread-safe scanner reads (ARCHITECTURE.md anti-pattern prevention)
- Default config matches D-17 exactly: `scan_folders=[], file_age_days=30, scan_interval_minutes=1440, file_types=[7 extensions]`

**src/__init__.py** — empty package initializer.

### Task 2 — Icon generator and requirements.txt (commit: 7c9d42c)

**src/icon.py** implements `create_icon_image()`:
- 64x64 RGBA PIL Image
- Rounded rectangle fill in #2563EB (accent blue per UI-SPEC)
- White "G" glyph centered using `textbbox` offset correction
- Segoe UI Bold (segoeuib.ttf) with `ImageFont.load_default()` fallback

**requirements.txt** — Phase 1 dependencies: `pystray>=0.19.5`, `Pillow>=10.0.0`

---

## Verification Results

All checks passed:

```
from src.events import OpenConfigEvent, ScanNowEvent, ShutdownEvent, ScanCompleteEvent  => OK
from src.config_store import ConfigStore; cs = ConfigStore()                             => OK, dir created
cs.get_config() => {'scan_folders': [], 'file_age_days': 30, ...}                       => OK
Round-trip: save file_age_days=60, reload ConfigStore() => 60                           => OK
from src.icon import create_icon_image; img.size                                         => (64, 64) OK
Icon center blue pixel: r=37 g=99 b=235 a=255                                           => #2563EB confirmed
```

---

## Deviations from Plan

None — plan executed exactly as written.

---

## Known Stubs

None — this plan creates foundational modules with no UI rendering paths. All exported values are fully functional.

---

## Self-Check: PASSED

All created files verified present on disk. Both task commits verified in git log.

## Commits

| Task | Commit | Message |
|------|--------|---------|
| 1 | 78251be | feat(01-01): add event dataclasses and ConfigStore with atomic persistence |
| 2 | 7c9d42c | feat(01-01): add Pillow icon generator and requirements.txt |
