---
phase: 01-core-scaffolding
plan: 02
subsystem: infra
tags: [pystray, tkinter, threading, queue, scheduler]

requires:
  - phase: 01-01
    provides: events.py (typed dataclass events), config_store.py (ConfigStore), icon.py (create_icon_image)

provides:
  - TrayApp — pystray Icon on main thread with Danish menu (Åbn indstillinger / Scan nu / Afslut)
  - UIThread — persistent hidden tk.Tk root on daemon thread with 100ms queue polling
  - ScanScheduler — threading.Event timeout loop with manual-only mode support
  - main.py — application entry point wiring all components in correct startup order

affects:
  - 01-03 (config dialog built on UIThread)
  - phase-02 (scan pipeline plugs into ScanNowEvent and ScanScheduler)
  - phase-03 (alert dialog added as Toplevel on existing UIThread root)

tech-stack:
  added: [pystray, tkinter (stdlib), threading (stdlib), queue (stdlib)]
  patterns:
    - Queue-mediated cross-thread communication (all events via queue.Queue)
    - pystray on main thread (Win32 constraint D-01)
    - tkinter on daemon worker thread (D-02, Pitfall 2)
    - Non-blocking queue poll via root.after(100) (D-04)
    - threading.Event timeout loop for interruptible scheduler sleep (D-18)

key-files:
  created:
    - src/tray_app.py
    - src/ui_thread.py
    - src/scheduler.py
    - src/main.py
  modified: []

key-decisions:
  - "pystray owns main thread (TrayApp.run() blocks); tkinter runs on daemon UIThread — hard Win32 constraint"
  - "All cross-thread events flow through a single queue.Queue — typed dataclass events from Plan 01"
  - "ScanScheduler uses threading.Event.wait(timeout=) not time.sleep() — allows immediate wakeup on stop()"
  - "_open_config_dialog in UIThread is a stub (logs only) — Plan 03 replaces with full Toplevel dialog"

patterns-established:
  - "Queue bridge pattern: tray callbacks post events, UIThread polls with get_nowait() every 100ms"
  - "Daemon threads for all worker components — process exits cleanly when main thread ends"
  - "Single hidden tk.Tk() root (withdrawn, never shown); all future dialogs are Toplevel children"

requirements-completed: [TRAY-01, TRAY-02, TRAY-03, TRAY-04, SCHED-01, SCHED-02, SCHED-03]

duration: 2min
completed: 2026-04-02
---

# Phase 01 Plan 02: Core Threading Architecture Summary

**pystray tray icon (main thread) wired to hidden tkinter root (daemon thread) via queue.Queue, with Event-based ScanScheduler skeleton and main.py startup sequence**

## Performance

- **Duration:** ~2 minutes
- **Started:** 2026-04-02T03:40:08Z
- **Completed:** 2026-04-02T03:42:00Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- TrayApp wraps pystray Icon with three Danish menu items; blocking `run()` must be called on main thread (Win32 constraint)
- UIThread creates a persistent hidden `tk.Tk()` root on a daemon thread and polls the shared queue every 100ms using `root.after()` — tkinter mainloop stays alive, no blocking `get()` calls
- ScanScheduler runs on a daemon thread with an interruptible `threading.Event.wait(timeout=interval_seconds)` loop; manual-only mode (`interval==0`) skips the timed loop entirely
- main.py starts components in the architecturally required order: ConfigStore → UIThread → ScanScheduler → TrayApp.run() (blocks) → scheduler.stop() → sys.exit(0)

## Task Commits

1. **Task 1: Create TrayApp, UIThread, and ScanScheduler** - `476ff1a` (feat)
2. **Task 2: Create main.py entry point wiring all components** - `9274135` (feat)

**Plan metadata:** (final docs commit — see below)

## Files Created/Modified

- `src/tray_app.py` — TrayApp class: pystray Icon with Danish menu, posts typed events to queue
- `src/ui_thread.py` — UIThread class: hidden tkinter root on daemon thread, 100ms queue polling, stub config dialog handler
- `src/scheduler.py` — ScanScheduler class: threading.Event timeout loop, manual-only mode, trigger_now() and stop()
- `src/main.py` — Application entry point: wires all components, logging with thread names, clean shutdown path

## Decisions Made

- `_open_config_dialog` is an intentional stub that logs "Config dialog requested" — Plan 03 replaces this with the full three-tab `tk.Toplevel` dialog. This keeps Plan 02 scope clean.
- Type annotation `def main() -> None:` used (plan acceptance criteria listed `def main():` without annotation, but annotated form is equivalent and preferred).

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

- `UIThread._open_config_dialog` in `src/ui_thread.py` — logs "Config dialog requested" only. Plan 03 (`01-03`) replaces this with the full config dialog `tk.Toplevel`. This is an intentional, documented stub per the plan spec.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Threading spine is complete; Phase 03 (config dialog) can now add `tk.Toplevel` as a child of the hidden root in `UIThread`
- Phase 02 (scan pipeline) can attach a `ScanNowEvent` handler to `UIThread._handle_event` and post events from `ScanScheduler._trigger_scan`
- Running `python src/main.py` from the project root will show the tray icon (manual verification at Plan 03 checkpoint)

## Self-Check: PASSED

All created files confirmed on disk. Both task commits (476ff1a, 9274135) confirmed in git log.

---
*Phase: 01-core-scaffolding*
*Completed: 2026-04-02*
