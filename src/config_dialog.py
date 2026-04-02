import queue
import tkinter as tk
import tkinter.ttk as ttk
import tkinter.filedialog as filedialog
import logging

from src.config_store import ConfigStore
from src.events import ScanNowEvent


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

    Tabs: Mapper | Regler | Scanning
    Opens from UIThread._open_config_dialog via tk.Toplevel(root).
    "Gem og luk" saves atomically via ConfigStore.save() and destroys dialog.
    X button discards changes and destroys dialog.
    """

    def __init__(self, root: tk.Tk, config_store: ConfigStore, event_queue: queue.Queue | None = None) -> None:
        self.root = root
        self.config_store = config_store
        self._event_queue = event_queue

        # Create Toplevel dialog (D-06: not a new tk.Tk root)
        self.dialog = tk.Toplevel(root)
        self.dialog.title("GDPR Scanner \u2014 Indstillinger")
        self.dialog.minsize(480, 380)

        # Center dialog on screen
        screen_width = self.dialog.winfo_screenwidth()
        screen_height = self.dialog.winfo_screenheight()
        x = (screen_width - 480) // 2
        y = (screen_height - 380) // 2
        self.dialog.geometry(f"+{x}+{y}")

        # X button discards changes (D-07 inverse — no save on close)
        self.dialog.protocol("WM_DELETE_WINDOW", self._on_close)

        # Load current config at dialog open time
        self._config = self.config_store.get_config()

        # Build notebook with 3 tabs
        self._notebook = ttk.Notebook(self.dialog)
        self._notebook.pack(expand=True, fill="both", padx=16, pady=(16, 0))

        self._build_mapper_tab()
        self._build_regler_tab()
        self._build_scanning_tab()

        # Footer: "Scan nu" left, "Gem og luk" right
        footer_frame = ttk.Frame(self.dialog)
        footer_frame.pack(fill="x", padx=16, pady=12)
        ttk.Button(
            footer_frame,
            text="Gem og luk",
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

    def _build_mapper_tab(self) -> None:
        """Tab 0: Mapper — folder list management."""
        frame = ttk.Frame(self._notebook)
        self._notebook.add(frame, text="Mapper")

        ttk.Label(
            frame,
            text="Mapper til scanning",
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w", padx=16, pady=(16, 8))

        # Listbox with vertical scrollbar
        list_frame = ttk.Frame(frame)
        list_frame.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical")
        scrollbar.pack(side="right", fill="y")

        self._folder_listbox = tk.Listbox(
            list_frame,
            selectmode=tk.SINGLE,
            height=8,
            yscrollcommand=scrollbar.set,
        )
        self._folder_listbox.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self._folder_listbox.yview)

        # Populate from config
        for folder in self._config.get("scan_folders", []):
            self._folder_listbox.insert(tk.END, folder)

        # Buttons row
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(anchor="w", padx=16, pady=(0, 16))

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

        # Enable/disable remove button on selection change
        self._folder_listbox.bind("<<ListboxSelect>>", self._on_listbox_select)

    def _build_regler_tab(self) -> None:
        """Tab 1: Regler — file age threshold + file type checkboxes."""
        frame = ttk.Frame(self._notebook)
        self._notebook.add(frame, text="Regler")

        # --- File age section ---
        ttk.Label(
            frame,
            text="Filaldergr\u00e6nse",
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w", padx=16, pady=(16, 4))

        ttk.Label(
            frame,
            text="Scan kun filer \u00e6ldre end:",
        ).pack(anchor="w", padx=16, pady=(0, 4))

        age_row = ttk.Frame(frame)
        age_row.pack(anchor="w", padx=16, pady=(0, 12))

        self._age_var = tk.IntVar(value=self._config.get("file_age_days", 30))
        ttk.Spinbox(
            age_row,
            from_=1,
            to=3650,
            textvariable=self._age_var,
            width=6,
        ).pack(side="left")
        ttk.Label(age_row, text="dage").pack(side="left", padx=(8, 0))

        # --- File types section ---
        ttk.Label(
            frame,
            text="Filtyper",
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w", padx=16, pady=(0, 4))

        types_frame = ttk.Frame(frame)
        types_frame.pack(anchor="w", padx=16, pady=(0, 16))

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
            ).grid(row=row, column=col, sticky="w", padx=8, pady=2)

    def _build_scanning_tab(self) -> None:
        """Tab 2: Scanning — scan frequency dropdown."""
        frame = ttk.Frame(self._notebook)
        self._notebook.add(frame, text="Scanning")

        ttk.Label(
            frame,
            text="Scanningsfrekvens",
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w", padx=16, pady=(16, 4))

        ttk.Label(
            frame,
            text="K\u00f8r automatisk scanning:",
        ).pack(anchor="w", padx=16, pady=(0, 8))

        current_minutes = self._config.get("scan_interval_minutes", 1440)
        self._freq_var = tk.StringVar()
        self._freq_var.set(
            FREQ_MINUTES_TO_DISPLAY.get(current_minutes, "Dagligt")
        )

        ttk.Combobox(
            frame,
            textvariable=self._freq_var,
            values=[label for label, _ in FREQUENCY_OPTIONS],
            state="readonly",
            width=20,
        ).pack(anchor="w", padx=16, pady=(0, 16))

        # --- Activity log section ---
        ttk.Label(
            frame,
            text="Aktivitetslog",
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w", padx=16, pady=(0, 4))

        log_frame = ttk.Frame(frame)
        log_frame.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        log_scroll = ttk.Scrollbar(log_frame, orient="vertical")
        log_scroll.pack(side="right", fill="y")

        self._log_text = tk.Text(
            log_frame,
            height=8,
            state="disabled",
            wrap="word",
            yscrollcommand=log_scroll.set,
            font=("Consolas", 8),
        )
        self._log_text.pack(side="left", fill="both", expand=True)
        log_scroll.config(command=self._log_text.yview)

        # Attach log handler so log messages appear in this widget
        self._log_handler = _TextLogHandler(self._log_text)
        self._log_handler.setLevel(logging.INFO)
        logging.getLogger().addHandler(self._log_handler)

        # Remove handler when dialog is destroyed
        self.dialog.bind("<Destroy>", self._on_destroy)

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def _add_folder(self) -> None:
        """Open folder picker; silently deduplicate per UI-SPEC."""
        folder = filedialog.askdirectory(parent=self.dialog)
        if not folder:
            return  # User cancelled
        # Silent deduplication — check existing listbox entries
        existing = list(self._folder_listbox.get(0, tk.END))
        if folder in existing:
            return
        self._folder_listbox.insert(tk.END, folder)

    def _remove_folder(self) -> None:
        """Remove selected folder from listbox."""
        selection = self._folder_listbox.curselection()
        if not selection:
            return
        self._folder_listbox.delete(selection[0])
        self._remove_btn.config(state="disabled")

    def _on_listbox_select(self, event) -> None:
        """Enable/disable Fjern valgt based on current selection."""
        if self._folder_listbox.curselection():
            self._remove_btn.config(state="normal")
        else:
            self._remove_btn.config(state="disabled")

    def _save_and_close(self) -> None:
        """Read all widget values, save atomically via ConfigStore, destroy dialog (D-07)."""
        folders = list(self._folder_listbox.get(0, tk.END))
        age = self._age_var.get()
        types = [ext for ext, var in self._type_vars.items() if var.get()]
        minutes = FREQ_DISPLAY_TO_MINUTES[self._freq_var.get()]

        config = {
            "scan_folders": folders,
            "file_age_days": age,
            "scan_interval_minutes": minutes,
            "file_types": types,
        }
        self.config_store.save(config)
        logging.info("Config saved: %s", config)
        self.dialog.destroy()

    def _on_close(self) -> None:
        """X button handler — discard changes, destroy dialog."""
        self.dialog.destroy()

    def _on_destroy(self, event) -> None:
        """Remove log handler when dialog is destroyed."""
        if event.widget == self.dialog:
            logging.getLogger().removeHandler(self._log_handler)

    def _trigger_scan(self) -> None:
        """Post ScanNowEvent to trigger an immediate scan."""
        if self._event_queue is not None:
            self._event_queue.put(ScanNowEvent())
            logging.info("Manuel scanning startet")
        else:
            logging.warning("Kan ikke starte scan — event queue ikke tilgængelig")
