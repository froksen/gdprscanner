import queue
import tkinter as tk
import tkinter.ttk as ttk
import tkinter.filedialog as filedialog
import logging

from src.config_store import ConfigStore
from src.events import ScanNowEvent
from src import styles


class _TextLogHandler(logging.Handler):
    """Append log records to a tk.Text widget (thread-safe via after())."""

    def __init__(self, text_widget: tk.Text) -> None:
        super().__init__()
        self._widget = text_widget
        self.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s", "%H:%M:%S"))

    def emit(self, record: logging.LogRecord) -> None:
        msg = self.format(record) + "\n"
        try:
            self._widget.after(0, self._append, msg)
        except Exception:
            pass

    def _append(self, msg: str) -> None:
        try:
            self._widget.config(state="normal")
            self._widget.insert(tk.END, msg)
            self._widget.see(tk.END)
            self._widget.config(state="disabled")
        except tk.TclError:
            pass


# Frequency mapping per D-10, D-11
FREQUENCY_OPTIONS = [
    ("Hvert 6. time", 360),
    ("Dagligt", 1440),
    ("Ugentligt", 10080),
    ("Kun manuelt", 0),
]
FREQ_DISPLAY_TO_MINUTES = {label: mins for label, mins in FREQUENCY_OPTIONS}
FREQ_MINUTES_TO_DISPLAY = {mins: label for label, mins in FREQUENCY_OPTIONS}

ALL_FILE_TYPES = [".docx", ".xlsx", ".xls", ".csv", ".pdf", ".txt", ".log"]


class ConfigDialog:
    """3-tab configuration dialog as tk.Toplevel.

    Tabs: Scanning | Mapper | Regler
    Opens from UIThread._open_config_dialog via tk.Toplevel(root).
    Changes are auto-saved on every widget interaction.
    X button and "Luk" both save and close.
    """

    def __init__(self, root: tk.Tk, config_store: ConfigStore, event_queue: queue.Queue | None = None) -> None:
        self.root = root
        self.config_store = config_store
        self._event_queue = event_queue

        # Create Toplevel dialog (D-06: not a new tk.Tk root)
        self.dialog = tk.Toplevel(root)
        self.dialog.configure(background=styles.BG)
        self.dialog.title("GDPR Scanner \u2014 Indstillinger")
        self.dialog.minsize(520, 420)

        # Center dialog on screen
        screen_width = self.dialog.winfo_screenwidth()
        screen_height = self.dialog.winfo_screenheight()
        x = (screen_width - 520) // 2
        y = (screen_height - 420) // 2
        self.dialog.geometry(f"+{x}+{y}")

        self.dialog.protocol("WM_DELETE_WINDOW", self._on_close)

        # Load current config at dialog open time
        self._config = self.config_store.get_config()

        # Build notebook — tabs in order: Scanning | Mapper | Regler
        self._notebook = ttk.Notebook(self.dialog)
        self._notebook.pack(expand=True, fill="both", padx=0, pady=(0, 0))

        self._build_scanning_tab()
        self._build_mapper_tab()
        self._build_regler_tab()

        # Auto-save: trace all scalar variables
        self._age_var.trace_add("write", self._autosave)
        self._freq_var.trace_add("write", self._autosave)
        for var in self._type_vars.values():
            var.trace_add("write", self._autosave)

        # Separator before footer
        ttk.Separator(self.dialog, orient="horizontal").pack(fill="x")

        # Footer
        footer_frame = ttk.Frame(self.dialog)
        footer_frame.pack(fill="x", padx=16, pady=10)
        ttk.Button(
            footer_frame,
            text="Luk",
            style="Primary.TButton",
            command=self._save_and_close,
        ).pack(side="right")
        ttk.Button(
            footer_frame,
            text="Scan nu",
            command=self._trigger_scan,
        ).pack(side="left")

    # ------------------------------------------------------------------
    # Tab builders
    # ------------------------------------------------------------------

    def _build_scanning_tab(self) -> None:
        """Tab 0: Scanning — scan frequency dropdown + activity log."""
        frame = ttk.Frame(self._notebook)
        frame.configure(style="TFrame")
        self._notebook.add(frame, text="  Scanning  ")

        # Section: Frequency
        ttk.Label(frame, text="Scanningsfrekvens",
                  style="SectionHeading.TLabel").pack(anchor="w", padx=20, pady=(18, 4))
        ttk.Label(frame, text="K\u00f8r automatisk scanning:",
                  style="Caption.TLabel").pack(anchor="w", padx=20, pady=(0, 6))

        current_minutes = self._config.get("scan_interval_minutes", 1440)
        self._freq_var = tk.StringVar()
        self._freq_var.set(FREQ_MINUTES_TO_DISPLAY.get(current_minutes, "Dagligt"))

        ttk.Combobox(
            frame,
            textvariable=self._freq_var,
            values=[label for label, _ in FREQUENCY_OPTIONS],
            state="readonly",
            width=22,
        ).pack(anchor="w", padx=20, pady=(0, 16))

        ttk.Separator(frame, orient="horizontal").pack(fill="x", padx=20, pady=(0, 14))

        # Section: Scan progress
        ttk.Label(frame, text="Scanning",
                  style="SectionHeading.TLabel").pack(anchor="w", padx=20, pady=(0, 6))

        self._progress_var = tk.IntVar(value=0)
        self._progress_bar = ttk.Progressbar(
            frame,
            orient="horizontal",
            mode="determinate",
            variable=self._progress_var,
            maximum=100,
        )
        self._progress_bar.pack(fill="x", padx=20, pady=(0, 4))

        self._progress_label = ttk.Label(frame, text="Klar", style="Caption.TLabel")
        self._progress_label.pack(anchor="w", padx=20, pady=(0, 14))

        ttk.Separator(frame, orient="horizontal").pack(fill="x", padx=20, pady=(0, 12))

        # Section: Activity log
        ttk.Label(frame, text="Aktivitetslog",
                  style="SectionHeading.TLabel").pack(anchor="w", padx=20, pady=(0, 6))

        log_outer = tk.Frame(frame, bg=styles.BG2, bd=0)
        log_outer.pack(fill="both", expand=True, padx=20, pady=(0, 4))

        log_scroll = ttk.Scrollbar(log_outer, orient="vertical")
        log_scroll.pack(side="right", fill="y")

        self._log_text = tk.Text(
            log_outer,
            height=8,
            state="disabled",
            wrap="word",
            yscrollcommand=log_scroll.set,
            font=("Consolas", 8),
            bg=styles.BG2,
            fg=styles.TEXT,
            relief="flat",
            borderwidth=0,
            padx=10,
            pady=6,
            insertbackground=styles.TEXT,
        )
        self._log_text.pack(side="left", fill="both", expand=True)
        log_scroll.config(command=self._log_text.yview)

        # Attach log handler
        self._log_handler = _TextLogHandler(self._log_text)
        self._log_handler.setLevel(logging.INFO)
        logging.getLogger().addHandler(self._log_handler)

        self.dialog.bind("<Destroy>", self._on_destroy)

    def _build_mapper_tab(self) -> None:
        """Tab 1: Mapper — folder list management."""
        frame = ttk.Frame(self._notebook)
        self._notebook.add(frame, text="  Mapper  ")

        ttk.Label(frame, text="Mapper til scanning",
                  style="SectionHeading.TLabel").pack(anchor="w", padx=20, pady=(18, 6))

        # Listbox with vertical scrollbar
        list_frame = tk.Frame(frame, bg=styles.BG, bd=1,
                              relief="solid", highlightthickness=0)
        list_frame.configure(background=styles.BORDER)
        list_frame.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical")
        scrollbar.pack(side="right", fill="y")

        self._folder_listbox = tk.Listbox(
            list_frame,
            selectmode=tk.SINGLE,
            height=8,
            yscrollcommand=scrollbar.set,
            bg=styles.BG,
            fg=styles.TEXT,
            selectbackground=styles.BLUE,
            selectforeground="white",
            activestyle="none",
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            font=("Segoe UI", 9),
        )
        self._folder_listbox.pack(side="left", fill="both", expand=True,
                                  padx=1, pady=1)
        scrollbar.config(command=self._folder_listbox.yview)

        # Populate from config
        for folder in self._config.get("scan_folders", []):
            self._folder_listbox.insert(tk.END, folder)

        # Buttons row
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(anchor="w", padx=20, pady=(0, 16))

        ttk.Button(
            btn_frame,
            text="Tilf\u00f8j mappe",
            command=self._add_folder,
        ).pack(side="left", padx=(0, 8))

        self._remove_btn = ttk.Button(
            btn_frame,
            text="Fjern valgt",
            command=self._remove_folder,
            state="disabled",
        )
        self._remove_btn.pack(side="left")

        self._folder_listbox.bind("<<ListboxSelect>>", self._on_listbox_select)

    def _build_regler_tab(self) -> None:
        """Tab 2: Regler — file age threshold + file type checkboxes."""
        frame = ttk.Frame(self._notebook)
        self._notebook.add(frame, text="  Regler  ")

        # --- File age section ---
        ttk.Label(frame, text="Filaldergr\u00e6nse",
                  style="SectionHeading.TLabel").pack(anchor="w", padx=20, pady=(18, 4))
        ttk.Label(frame, text="Scan kun filer \u00e6ldre end (0 = alle filer):",
                  style="Caption.TLabel").pack(anchor="w", padx=20, pady=(0, 6))

        age_row = ttk.Frame(frame)
        age_row.pack(anchor="w", padx=20, pady=(0, 16))

        self._age_var = tk.IntVar(value=self._config.get("file_age_days", 30))
        ttk.Spinbox(
            age_row,
            from_=0,
            to=3650,
            textvariable=self._age_var,
            width=6,
        ).pack(side="left")
        ttk.Label(age_row, text="dage", style="Caption.TLabel").pack(side="left", padx=(8, 0))

        ttk.Separator(frame, orient="horizontal").pack(fill="x", padx=20, pady=(0, 14))

        # --- File types section ---
        ttk.Label(frame, text="Filtyper",
                  style="SectionHeading.TLabel").pack(anchor="w", padx=20, pady=(0, 8))

        types_frame = ttk.Frame(frame)
        types_frame.pack(anchor="w", padx=20, pady=(0, 16))

        configured_types = self._config.get("file_types", [])
        self._type_vars: dict[str, tk.BooleanVar] = {}
        for i, ext in enumerate(ALL_FILE_TYPES):
            var = tk.BooleanVar(value=(ext in configured_types))
            self._type_vars[ext] = var
            row = i // 3
            col = i % 3
            ttk.Checkbutton(
                types_frame,
                text=ext,
                variable=var,
            ).grid(row=row, column=col, sticky="w", padx=(0, 20), pady=3)

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def _add_folder(self) -> None:
        """Open folder picker; silently deduplicate."""
        folder = filedialog.askdirectory(parent=self.dialog)
        if not folder:
            return
        existing = list(self._folder_listbox.get(0, tk.END))
        if folder in existing:
            return
        self._folder_listbox.insert(tk.END, folder)
        self._autosave()

    def _remove_folder(self) -> None:
        """Remove selected folder from listbox."""
        selection = self._folder_listbox.curselection()
        if not selection:
            return
        self._folder_listbox.delete(selection[0])
        self._remove_btn.config(state="disabled")
        self._autosave()

    def _on_listbox_select(self, event) -> None:
        """Enable/disable Fjern valgt based on current selection."""
        if self._folder_listbox.curselection():
            self._remove_btn.config(state="normal")
        else:
            self._remove_btn.config(state="disabled")

    def _collect_config(self) -> dict:
        """Read all widget values and return config dict."""
        return {
            "scan_folders": list(self._folder_listbox.get(0, tk.END)),
            "file_age_days": self._age_var.get(),
            "scan_interval_minutes": FREQ_DISPLAY_TO_MINUTES[self._freq_var.get()],
            "file_types": [ext for ext, var in self._type_vars.items() if var.get()],
        }

    def _autosave(self, *_) -> None:
        """Save current widget values immediately."""
        config = self._collect_config()
        self.config_store.save(config)
        logging.debug("Config auto-gemt")

    def _save_and_close(self) -> None:
        """Save and destroy dialog."""
        self._autosave()
        logging.info("Config gemt og dialog lukket")
        self.dialog.destroy()

    def _on_close(self) -> None:
        """X button handler — save and destroy dialog."""
        self._autosave()
        self.dialog.destroy()

    def _on_destroy(self, event) -> None:
        """Remove log handler when dialog is destroyed."""
        if event.widget == self.dialog:
            logging.getLogger().removeHandler(self._log_handler)

    def set_scan_progress(self, current: int, total: int, current_file: str) -> None:
        """Update the progress bar and current-file label (called from UIThread)."""
        pct = int(current / total * 100) if total > 0 else 0
        self._progress_var.set(pct)
        filename = current_file.split("\\")[-1].split("/")[-1]
        self._progress_label.configure(
            text=f"Fil {current} af {total}: {filename}"
        )

    def set_scan_idle(self) -> None:
        """Reset progress display when scan completes."""
        self._progress_var.set(0)
        self._progress_label.configure(text="Klar")

    def _trigger_scan(self) -> None:
        """Post ScanNowEvent to trigger an immediate scan."""
        if self._event_queue is not None:
            self._event_queue.put(ScanNowEvent())
            logging.info("Manuel scanning startet")
        else:
            logging.warning("Kan ikke starte scan — event queue ikke tilgængelig")
