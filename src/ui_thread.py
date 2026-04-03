import os
import queue
import threading
import logging
import tkinter as tk
import tkinter.ttk as ttk

from src.config_store import ConfigStore
from src.events import OpenConfigEvent, ScanNowEvent, ShutdownEvent, ScanCompleteEvent, FindingEvent, FileFinding, ScanProgressEvent
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
        elif isinstance(event, ScanProgressEvent):
            self._update_scan_progress(event)
        elif isinstance(event, ScanCompleteEvent):
            self._on_scan_complete(event)

    def _run_scan(self) -> None:
        def _progress(current: int, total: int, current_file: str) -> None:
            self.event_queue.put(ScanProgressEvent(current=current, total=total, current_file=current_file))

        result = self.scan_engine.scan(progress_callback=_progress)

        # Group all findings by file — one FindingEvent per file
        grouped: dict = {}
        for f in result.findings:
            if f.path not in grouped:
                grouped[f.path] = FindingEvent(path=f.path, age_days=f.age_days, findings=[])
            grouped[f.path].findings.append(FileFinding(
                reason=f.reason, snippet=f.snippet, line_number=f.line_number
            ))

        for event in grouped.values():
            logging.info("Fund i '%s': %d træffere", event.path, len(event.findings))
            self.event_queue.put(event)

        self.event_queue.put(ScanCompleteEvent(files_scanned=result.files_scanned, findings_count=len(result.findings)))

    def _update_scan_progress(self, event: ScanProgressEvent) -> None:
        if self._config_dialog is not None:
            try:
                self._config_dialog.set_scan_progress(event.current, event.total, event.current_file)
            except tk.TclError:
                pass

    def _on_scan_complete(self, event: ScanCompleteEvent) -> None:
        logging.info("Scan complete: %d files scanned, %d findings", event.files_scanned, event.findings_count)
        if self._config_dialog is not None:
            try:
                self._config_dialog.set_scan_idle()
            except tk.TclError:
                pass

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
        n = len(event.findings)
        header_text = f"  Fundet {n} GDPR-tr\u00e6ffer i fil"

        dlg = tk.Toplevel(self.root)
        dlg.withdraw()
        dlg.configure(background=styles.BG)
        dlg.title("GDPR Scanner \u2014 Fundet PII")
        dlg.grab_set()
        dlg.minsize(560, 380)
        dlg.resizable(True, True)
        self._finding_dialog = dlg

        # Header band
        header = tk.Frame(dlg, bg=styles.BLUE, height=52)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header,
            text=header_text,
            bg=styles.BLUE, fg="white",
            font=("Segoe UI", 10, "bold"),
            anchor="w",
        ).place(relx=0, rely=0.5, anchor="w", x=12)

        # Body
        body = tk.Frame(dlg, bg=styles.BG)
        body.pack(fill="both", expand=True, padx=20, pady=(14, 4))

        # File info
        info_frame = tk.Frame(body, bg=styles.BG)
        info_frame.pack(fill="x")

        def _info_row(parent, label, value):
            row = tk.Frame(parent, bg=styles.BG)
            row.pack(fill="x", pady=2)
            tk.Label(row, text=label, bg=styles.BG, fg=styles.TEXT2,
                     font=("Segoe UI", 9), width=10, anchor="w").pack(side="left")
            tk.Label(row, text=value, bg=styles.BG, fg=styles.TEXT,
                     font=("Segoe UI", 9), anchor="w", wraplength=420).pack(side="left")

        _info_row(info_frame, "Fil:", event.path)
        if event.age_days is not None:
            _info_row(info_frame, "Alder:", f"{event.age_days} dage")

        # Separator
        tk.Frame(body, bg=styles.BORDER, height=1).pack(fill="x", pady=(10, 6))

        # Findings table
        tree_frame = tk.Frame(body, bg=styles.BG)
        tree_frame.pack(fill="both", expand=True)

        cols = ("type", "linje", "fundsted")
        tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=6)
        tree.heading("type", text="Type")
        tree.heading("linje", text="Linje")
        tree.heading("fundsted", text="Fundsted")
        tree.column("type", width=160, stretch=False)
        tree.column("linje", width=55, stretch=False, anchor="center")
        tree.column("fundsted", width=300, stretch=True)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        for f in event.findings:
            linje = str(f.line_number) if f.line_number is not None else ""
            fundsted = f.snippet or ""
            tree.insert("", "end", values=(f.reason, linje, fundsted))

        # Action buttons
        sep = tk.Frame(dlg, bg=styles.BORDER, height=1)
        sep.pack(fill="x", padx=20, pady=(10, 0))

        btn_frame = ttk.Frame(dlg)
        btn_frame.pack(fill="x", padx=16, pady=12)

        ttk.Button(btn_frame, text="\u00c5bn fil",
                   command=lambda: self._open_file(event.path)).pack(side="left", padx=(0, 6))
        ttk.Button(btn_frame, text="Slet fil", style="Danger.TButton",
                   command=lambda: self._handle_finding_action(event, "delete")).pack(side="left", padx=(0, 6))
        ttk.Button(btn_frame, text="Behold",
                   command=lambda: self._handle_finding_action(event, "keep")).pack(side="left", padx=(0, 6))
        ttk.Button(btn_frame, text="Ignorer permanent",
                   command=lambda: self._handle_finding_action(event, "ignore")).pack(side="left", padx=(0, 6))
        ttk.Button(btn_frame, text="Afbryd scanning",
                   command=self._abort_scan).pack(side="right")

        # Centre on screen
        dlg.update_idletasks()
        w = dlg.winfo_reqwidth()
        h = dlg.winfo_reqheight()
        sw = dlg.winfo_screenwidth()
        sh = dlg.winfo_screenheight()
        dlg.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")
        dlg.deiconify()

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
            "Navn match": "Filen indeholder et personnavn, som er personoplysninger under GDPR.",
            "Adresse match": "Filen indeholder en dansk postadresse, som er personoplysninger under GDPR.",
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
