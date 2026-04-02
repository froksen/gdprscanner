# Roadmap: GDPR Scanner

## Overview

Four phases take this project from an empty repo to a distributable Windows tray application. Phase 1 establishes the hard architectural foundation — pystray on the main thread, tkinter on a worker thread, config persisted atomically. Phase 2 builds the scan pipeline on top of that skeleton: file filtering, content extraction across five formats, and deterministic PII detection. Phase 3 closes the user decision loop with the alert dialog and ignore list, making the application genuinely useful. Phase 4 packages everything into a self-contained Windows executable tested on a clean machine.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Core Scaffolding** - pystray/tkinter threading architecture, config dialog, persistence, scheduler skeleton
- [x] **Phase 2: Scan Pipeline** - File filtering, content extraction (docx/xlsx/csv/pdf/txt), PII detection (CPR/email/phone/headers)
- [x] **Phase 3: Alert Dialog & Ignore List** - User decision loop (Delete/Keep/Ignore permanent), ignore list persistence
- [ ] **Phase 4: Packaging** - PyInstaller onedir .exe with .spec file, tested on clean Windows environment

## Phase Details

### Phase 1: Core Scaffolding
**Goal**: Users can run the application as a background tray process that persists their configuration between sessions
**Depends on**: Nothing (first phase)
**Requirements**: TRAY-01, TRAY-02, TRAY-03, TRAY-04, CONF-01, CONF-02, CONF-03, CONF-04, CONF-05, CONF-06, SCHED-01, SCHED-02, SCHED-03
**Success Criteria** (what must be TRUE):
  1. Application starts directly into the Windows system tray with no visible window — the tray icon appears within 2 seconds of launch
  2. Right-clicking the tray icon shows a menu with "Abn indstillinger", "Scan nu", and "Afslut" — all items respond to clicks without freezing the tray
  3. The configuration dialog opens from the tray menu and lets the user add/remove folders, set file age threshold, set scan frequency, and choose file types — then saves those settings
  4. Settings written to `%APPDATA%\GDPRScanner\config.json` survive a full application restart
  5. The scheduled scanner fires at the configured interval in the background without making the UI unresponsive
**Plans:** 3 plans
Plans:
- [x] 01-01-PLAN.md — Events, ConfigStore, tray icon image, requirements.txt
- [x] 01-02-PLAN.md — TrayApp, UIThread, ScanScheduler, main.py entry point
- [x] 01-03-PLAN.md — 3-tab ConfigDialog and UIThread wiring (human verified 2026-04-02)
**UI hint**: yes

### Phase 2: Scan Pipeline
**Goal**: The scheduler can walk configured folders and emit findings for any file containing detectable PII
**Depends on**: Phase 1
**Requirements**: FILT-01, FILT-02, FILT-03, FILT-04, SCAN-01, SCAN-02, SCAN-03, SCAN-04, SCAN-05, SCAN-06, SCAN-07, SCAN-08, SCAN-09
**Success Criteria** (what must be TRUE):
  1. Files younger than the configured age threshold and files on the ignore list are not opened or processed
  2. A .docx, .xlsx, .csv, .pdf, .txt, or .log file containing a valid CPR number (including post-2007 numbers), a Danish email address, or a Danish phone number is flagged as a finding
  3. A spreadsheet with a column header matching "CPR", "Navn", "Adresse", "Fodselsdato", or equivalent is flagged even if the cell values themselves do not match a PII pattern
  4. A file whose name contains "cpr", "kunde", "patient", "personnummer", "kaldenavn", "adresse", or "fortrolig" is flagged at the filename layer before content is read
  5. A malformed Office file or a PDF over 20 MB does not crash the scan run — the file is skipped and remaining files continue to be processed
**Plans:** 3 plans
Plans:
- [x] 02-01-PLAN.md — PII detectors (CPR/email/phone/headers/filename) + FindingEvent + tests
- [x] 02-02-PLAN.md — Content extractors for all file types (docx/xlsx/csv/pdf/txt/log) + tests
- [x] 02-03-PLAN.md — ScanEngine orchestration + file filtering + scheduler wiring

### Phase 3: Alert Dialog & Ignore List
**Goal**: Users can act on each finding — deleting, keeping, or permanently ignoring the file — and the ignore list persists across sessions
**Depends on**: Phase 2
**Requirements**: ALRT-01, ALRT-02, ALRT-03, ALRT-04, ALRT-05, ALRT-06, IGNR-01, IGNR-02, IGNR-03
**Success Criteria** (what must be TRUE):
  1. When a finding arrives, a dialog appears showing the file name, full path, file age, and which detection rule triggered the alert
  2. Choosing "Slet fil" deletes the file from disk after a confirmation prompt and closes the dialog
  3. Choosing "Behold" closes the dialog without modifying the file — the same file will be flagged again on the next scan
  4. Choosing "Ignorer permanent" adds the file path to the ignore list so the file is never flagged again, and the ignore list survives a full application restart
  5. When multiple findings exist, dialogs appear one at a time — a second dialog does not open until the user has acted on the first
**Plans**: TBD
**UI hint**: yes

### Phase 4: Packaging
**Goal**: The application runs as a self-contained Windows executable on a machine with no Python installation
**Depends on**: Phase 3
**Requirements**: (no dedicated v1 requirement IDs — packaging is the delivery mechanism for all prior requirements)
**Success Criteria** (what must be TRUE):
  1. Running `GDPRScanner\GDPRScanner.exe` on a clean Windows machine (no Python, no pip packages) starts the application and shows the tray icon
  2. No console window appears when the application launches
  3. All Phase 1-3 success criteria pass when exercised against the packaged executable, not the source script
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Core Scaffolding | 3/3 | Complete | 2026-04-02 |
| 2. Scan Pipeline | 3/3 | Complete | 2026-04-02 |
| 3. Alert Dialog & Ignore List | 0/? | Complete | 2026-04-02 |
| 4. Packaging | 0/? | Not started | - |
