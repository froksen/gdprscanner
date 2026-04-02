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
from src import styles


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

        styles.apply_theme(self.root)

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
                    line_number=finding.line_number,
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
        accent, accent_bg = styles.severity_colors(event.reason)

        dlg = tk.Toplevel(self.root)
        dlg.configure(background=styles.BG)
        dlg.title("GDPR Scanner — Fundet PII")
        dlg.grab_set()
        dlg.minsize(520, 320)
        dlg.resizable(True, False)
        self._finding_dialog = dlg

        # Coloured header band
        header = tk.Frame(dlg, bg=accent, height=52)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header,
            text=f"  {event.reason}",
            bg=accent, fg="white",
            font=("Segoe UI", 10, "bold"),
            anchor="w",
        ).place(relx=0, rely=0.5, anchor="w", x=12)

        # Body
        body = tk.Frame(dlg, bg=styles.BG)
        body.pack(fill="both", expand=True, padx=20, pady=(14, 4))

        # Violation description
        desc = self._get_violation_description(event.reason)
        tk.Label(
            body, text=desc, bg=styles.BG, fg=styles.TEXT2,
            font=("Segoe UI", 9), wraplength=460, justify="left", anchor="w",
        ).pack(anchor="w", pady=(0, 10))

        # Separator
        tk.Frame(body, bg=styles.BORDER, height=1).pack(fill="x", pady=(0, 10))

        # File info grid
        info_frame = tk.Frame(body, bg=styles.BG)
        info_frame.pack(fill="x")

        def _info_row(parent, label, value, value_color=styles.TEXT):
            row = tk.Frame(parent, bg=styles.BG)
            row.pack(fill="x", pady=2)
            tk.Label(row, text=label, bg=styles.BG, fg=styles.TEXT2,
                     font=("Segoe UI", 9), width=10, anchor="w").pack(side="left")
            tk.Label(row, text=value, bg=styles.BG, fg=value_color,
                     font=("Segoe UI", 9), anchor="w", wraplength=380).pack(side="left")

        _info_row(info_frame, "Fil:", event.path)
        if event.age_days is not None:
            _info_row(info_frame, "Alder:", f"{event.age_days} dage")

        # Snippet box
        if event.snippet:
            loc = f"Linje {event.line_number}: " if event.line_number is not None else ""
            snip_outer = tk.Frame(body, bg=accent_bg, bd=0)
            snip_outer.pack(fill="x", pady=(10, 0))
            tk.Label(snip_outer, text="Fundsted", bg=accent_bg, fg=styles.TEXT2,
                     font=("Segoe UI", 8)).pack(anchor="w", padx=10, pady=(6, 2))
            snip_text = tk.Text(
                snip_outer, height=2, wrap="word", font=("Consolas", 9),
                bg=accent_bg, fg=styles.TEXT, relief="flat",
                borderwidth=0, padx=10, pady=4, state="normal",
            )
            snip_text.insert("1.0", f"{loc}{event.snippet}")
            snip_text.configure(state="disabled")
            snip_text.pack(fill="x", padx=0, pady=(0, 8))

        # Action buttons
        sep = tk.Frame(dlg, bg=styles.BORDER, height=1)
        sep.pack(fill="x", padx=20, pady=(10, 0))

        btn_frame = ttk.Frame(dlg)
        btn_frame.pack(fill="x", padx=16, pady=12)

        ttk.Button(btn_frame, text="Åbn fil",
                   command=lambda: self._open_file(event.path)).pack(side="left", padx=(0, 6))
        ttk.Button(btn_frame, text="Slet fil", style="Danger.TButton",
                   command=lambda: self._handle_finding_action(event, "delete")).pack(side="left", padx=(0, 6))
        ttk.Button(btn_frame, text="Behold",
                   command=lambda: self._handle_finding_action(event, "keep")).pack(side="left", padx=(0, 6))
        ttk.Button(btn_frame, text="Ignorer permanent",
                   command=lambda: self._handle_finding_action(event, "ignore")).pack(side="left", padx=(0, 6))
        ttk.Button(btn_frame, text="Afbryd scanning",
                   command=self._abort_scan).pack(side="right")

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

    def _open_file(self, path: str) -> None:
        """Open file with default application."""
        try:
            os.startfile(path)
        except Exception as e:
            logging.warning("Kunne ikke åbne fil '%s': %s", path, e)

    def _get_violation_description(self, reason: str) -> str:
        descriptions = {
            "CPR match": "Filen indeholder et dansk CPR-nummer — fortrolige personoplysninger under dansk databeskyttelseslov § 11.",
            "Email match": "Filen indeholder en e-mailadresse, som er personlige oplysninger under GDPR.",
            "Phone match": "Filen indeholder et dansk telefonnummer, som er personlige oplysninger.",
            "IBAN match": "Filen indeholder et dansk IBAN-nummer (bankkontooplysninger), som er personlige oplysninger.",
            "Kreditkortnummer match": "Filen indeholder et kreditkortnummer, som er følsomme finansielle personoplysninger.",
            "Spreadsheet header indicates PII": "Regnearket har kolonneoverskrifter der tyder på personoplysninger (f.eks. CPR, Navn).",
        }
        if reason.startswith("Filename contains keyword"):
            return "Filnavnet indeholder ord der tyder på følsomt indhold (f.eks. 'cpr', 'journal', 'straffeattest')."
        if reason.startswith("Særlig kategori:"):
            category = reason.replace("Særlig kategori: ", "")
            return (
                f"Filen indeholder nøgleord der tyder på særlig kategori af personoplysninger: {category}. "
                "Disse kræver eksplicit retsgrundlag under GDPR art. 9."
            )
        return descriptions.get(reason, "Filen indeholder potentielt følsomme personoplysninger.")

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
