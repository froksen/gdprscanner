import os
import queue
import threading
import logging
import tkinter as tk
import tkinter.ttk as ttk

from src.config_store import ConfigStore
from src.events import OpenConfigEvent, ScanNowEvent, ShutdownEvent, ScanCompleteEvent, FindingEvent
from src.config_dialog import ConfigDialog
from src.scan_engine import ScanEngine


class UIThread:
    """Runs a persistent tkinter mainloop on a daemon worker thread.

    Per D-02 and Pitfall 2, tkinter must not share the main thread with
    pystray.  A single hidden tk.Tk() root is created here; all dialogs
    are tk.Toplevel children of that root (one Tk root per process — D-06).

    Cross-thread communication uses root.after() to marshal calls back
    onto this thread, combined with queue polling every 100 ms (D-04).
    """

    def __init__(self, event_queue: queue.Queue, config_store: ConfigStore) -> None:
        self.event_queue = event_queue
        self.config_store = config_store
        self.root = None
        self._config_dialog = None
        self.scan_engine = ScanEngine(config_store)
        self._finding_queue: list[FindingEvent] = []
        self._finding_dialog = None

    def start(self) -> threading.Thread:
        """Create and start the daemon UI thread.  Returns the Thread object."""
        t = threading.Thread(target=self._run, daemon=True, name="UIThread")
        t.start()
        return t

    # ------------------------------------------------------------------
    # Internal thread body
    # ------------------------------------------------------------------

    def _run(self) -> None:
        self.root = tk.Tk()
        self.root.withdraw()  # hidden root — never shown (Pitfall 2)

        # Apply Windows-native theme; fall back gracefully on other platforms
        try:
            ttk.Style().theme_use("vista")
        except tk.TclError:
            try:
                ttk.Style().theme_use("clam")
            except tk.TclError:
                pass

        self._poll_queue()
        self.root.mainloop()

    def _poll_queue(self) -> None:
        """Non-blocking queue drain — runs every 100 ms via root.after().

        Using get_nowait() (not get()) keeps the tkinter mainloop alive.
        See ARCHITECTURE.md anti-pattern: "Blocking queue.get() inside
        tkinter after() callback".
        """
        try:
            event = self.event_queue.get_nowait()
            self._handle_event(event)
        except queue.Empty:
            pass
        self.root.after(100, self._poll_queue)

    def _handle_event(self, event) -> None:
        if isinstance(event, OpenConfigEvent):
            self._open_config_dialog()
        elif isinstance(event, ShutdownEvent):
            self.root.quit()
        elif isinstance(event, ScanNowEvent):
            logging.info("ScanNowEvent received by UI thread")
            threading.Thread(target=self._run_scan, daemon=True, name="ScanWorker").start()
        elif isinstance(event, FindingEvent):
            self._enqueue_finding(event)

    def _run_scan(self) -> None:
        result = self.scan_engine.scan()
        for finding in result.findings:
            logging.info("Finding: %s: %s %s", finding.path, finding.reason, finding.snippet or "")
            self.event_queue.put(
                FindingEvent(
                    path=finding.path,
                    reason=finding.reason,
                    snippet=finding.snippet,
                    age_days=finding.age_days,
                )
            )
        self.event_queue.put(ScanCompleteEvent(files_scanned=result.files_scanned, findings_count=len(result.findings)))

    def _enqueue_finding(self, finding_event: FindingEvent) -> None:
        self._finding_queue.append(finding_event)
        self._show_next_finding_if_idle()

    def _show_next_finding_if_idle(self) -> None:
        if self._finding_dialog is not None:
            return
        if not self._finding_queue:
            return

        event = self._finding_queue.pop(0)
        self._show_finding_dialog(event)

    def _show_finding_dialog(self, event: FindingEvent) -> None:
        self._finding_dialog = tk.Toplevel(self.root)
        self._finding_dialog.title("GDPR Scanner — Fundet PII")
        self._finding_dialog.grab_set()

        ttl = f"Fundet: {event.reason}"
        ttk.Label(self._finding_dialog, text=ttl, font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=16, pady=(16, 4))

        # Description of violation
        desc = self._get_violation_description(event.reason)
        ttk.Label(self._finding_dialog, text=desc, wraplength=400).pack(anchor="w", padx=16, pady=(0, 8))

        ttk.Label(self._finding_dialog, text=f"Fil: {event.path}").pack(anchor="w", padx=16, pady=(0, 4))
        if event.age_days is not None:
            ttk.Label(self._finding_dialog, text=f"Filalder: {event.age_days} dage").pack(anchor="w", padx=16, pady=(0, 4))
        if event.snippet:
            ttk.Label(self._finding_dialog, text=f"Snippet: {event.snippet}").pack(anchor="w", padx=16, pady=(0, 4))

        button_frame = ttk.Frame(self._finding_dialog)
        button_frame.pack(fill="x", padx=16, pady=16)

        ttk.Button(button_frame, text="Slet fil", command=lambda: self._handle_finding_action(event, "delete")).pack(side="left", padx=4)
        ttk.Button(button_frame, text="Behold", command=lambda: self._handle_finding_action(event, "keep")).pack(side="left", padx=4)
        ttk.Button(button_frame, text="Ignorer permanent", command=lambda: self._handle_finding_action(event, "ignore")).pack(side="left", padx=4)
        ttk.Button(button_frame, text="Afbryd scanning", command=self._abort_scan).pack(side="right", padx=4)

    def _handle_finding_action(self, event: FindingEvent, action: str) -> None:
        if action == "delete":
            import tkinter.messagebox as messagebox
            if messagebox.askyesno("Bekræft sletning", f"Er du sikker på at du vil slette filen?\n{event.path}"):
                try:
                    os.remove(event.path)
                    logging.info("Deleted file via alert action: %s", event.path)
                except Exception as e:
                    logging.warning("Failed deleting file '%s': %s", event.path, e)
        elif action == "ignore":
            self.config_store.add_ignore_path(event.path)
            logging.info("Added file to ignore list: %s", event.path)
        elif action == "keep":
            logging.info("Kept file: %s", event.path)

        if self._finding_dialog is not None:
            self._finding_dialog.destroy()
            self._finding_dialog = None

        self._show_next_finding_if_idle()

    def _get_violation_description(self, reason: str) -> str:
        descriptions = {
            "CPR match": "Filen indeholder et dansk CPR-nummer, som er følsomme personoplysninger under GDPR.",
            "Email match": "Filen indeholder en dansk e-mailadresse (.dk), som kan være personlige oplysninger.",
            "Phone match": "Filen indeholder et dansk telefonnummer, som er personlige oplysninger.",
            "Spreadsheet header indicates PII": "Regnearket har kolonneoverskrifter der tyder på personoplysninger (f.eks. CPR, Navn).",
        }
        if reason.startswith("Filename contains keyword"):
            return "Filnavnet indeholder ord der tyder på følsomt indhold (f.eks. 'cpr', 'kunde')."
        return descriptions.get(reason, "Filen indeholder potentielt følsomme oplysninger.")

    def _abort_scan(self) -> None:
        logging.info("Scan aborted by user")
        self._finding_queue.clear()
        if self._finding_dialog is not None:
            self._finding_dialog.destroy()
            self._finding_dialog = None

    def _open_config_dialog(self) -> None:
        """Open config dialog as Toplevel child of hidden root.

        If dialog already exists and is visible, bring it to front (no duplicates).
        Per D-06: dialog is tk.Toplevel, not new tk.Tk.
        Called from _handle_event which runs on the tkinter thread via root.after().
        """
        if self._config_dialog is not None:
            try:
                self._config_dialog.dialog.lift()
                self._config_dialog.dialog.focus_force()
                return
            except tk.TclError:
                # Dialog was destroyed; clear reference and create a new one
                self._config_dialog = None

        self._config_dialog = ConfigDialog(self.root, self.config_store, self.event_queue)
