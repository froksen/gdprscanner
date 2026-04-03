import queue
import tkinter as tk
import tkinter.ttk as ttk
import tkinter.filedialog as filedialog
import logging

from src.config_store import ConfigStore
from src.events import ScanNowEvent
from src import styles
from src.scan_engine import ALL_DETECTION_TYPES


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
        for var in self._detection_vars.values():
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
        """Tab 1: Mapper — folder list with per-folder recursive toggle."""
        frame = ttk.Frame(self._notebook)
        self._notebook.add(frame, text="  Mapper  ")

        ttk.Label(frame, text="Mapper til scanning",
                  style="SectionHeading.TLabel").pack(anchor="w", padx=20, pady=(18, 6))

        # Treeview with two columns: path and recursive flag
        tree_frame = tk.Frame(frame, bg=styles.BORDER, bd=1, relief="flat")
        tree_frame.pack(fill="both", expand=True, padx=20, pady=(0, 8))

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical")
        scrollbar.pack(side="right", fill="y")

        self._folder_tree = ttk.Treeview(
            tree_frame,
            columns=("path", "recursive"),
            show="headings",
            selectmode="browse",
            yscrollcommand=scrollbar.set,
            height=8,
        )
        self._folder_tree.heading("path", text="Mappe")
        self._folder_tree.heading("recursive", text="Undermapper")
        self._folder_tree.column("path", stretch=True, minwidth=200)
        self._folder_tree.column("recursive", width=110, anchor="center", stretch=False)
        self._folder_tree.pack(side="left", fill="both", expand=True, padx=1, pady=1)
        scrollbar.config(command=self._folder_tree.yview)

        # Populate from config
        for entry in self._config.get("scan_folders", []):
            path = entry["path"] if isinstance(entry, dict) else entry
            recursive = entry.get("recursive", True) if isinstance(entry, dict) else True
            self._folder_tree.insert("", tk.END, values=(path, "✓ Ja" if recursive else "✗ Nej"))

        self._folder_tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        # Buttons row
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(anchor="w", padx=20, pady=(0, 16))

        ttk.Button(btn_frame, text="Tilføj mappe",
                   command=self._add_folder).pack(side="left", padx=(0, 8))

        self._remove_btn = ttk.Button(btn_frame, text="Fjern valgt",
                                      command=self._remove_folder, state="disabled")
        self._remove_btn.pack(side="left", padx=(0, 8))

        self._recursive_btn = ttk.Button(btn_frame, text="Skift undermapper",
                                         command=self._toggle_recursive, state="disabled")
        self._recursive_btn.pack(side="left")

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

        ttk.Separator(frame, orient="horizontal").pack(fill="x", padx=20, pady=(4, 14))

        # --- Detection types section ---
        ttk.Label(frame, text="GDPR-elementer at søge efter",
                  style="SectionHeading.TLabel").pack(anchor="w", padx=20, pady=(0, 8))

        enabled_detection = set(self._config.get("detection_types",
                                                  [dt[0] for dt in ALL_DETECTION_TYPES]))
        self._detection_vars: dict[str, tk.BooleanVar] = {}

        # Group checkboxes by group name
        current_group = None
        group_frame = None
        col_count = 0
        row_count = 0
        for det_id, label, group in ALL_DETECTION_TYPES:
            if group != current_group:
                current_group = group
                ttk.Label(frame, text=group, style="Caption.TLabel").pack(
                    anchor="w", padx=20, pady=(4, 2))
                group_frame = ttk.Frame(frame)
                group_frame.pack(anchor="w", padx=20, pady=(0, 4))
                col_count = 0
                row_count = 0

            var = tk.BooleanVar(value=(det_id in enabled_detection))
            self._detection_vars[det_id] = var
            ttk.Checkbutton(group_frame, text=label, variable=var).grid(
                row=row_count, column=col_count, sticky="w", padx=(0, 20), pady=2)
            col_count += 1
            if col_count >= 2:
                col_count = 0
                row_count += 1

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def _add_folder(self) -> None:
        """Open folder picker; silently deduplicate."""
        folder = filedialog.askdirectory(parent=self.dialog)
        if not folder:
            return
        existing = [self._folder_tree.item(iid, "values")[0]
                    for iid in self._folder_tree.get_children()]
        if folder in existing:
            return
        self._folder_tree.insert("", tk.END, values=(folder, "✓ Ja"))
        self._autosave()

    def _remove_folder(self) -> None:
        """Remove selected folder from treeview."""
        selected = self._folder_tree.selection()
        if not selected:
            return
        self._folder_tree.delete(selected[0])
        self._remove_btn.config(state="disabled")
        self._recursive_btn.config(state="disabled")
        self._autosave()

    def _toggle_recursive(self) -> None:
        """Toggle the recursive (undermapper) flag for the selected folder."""
        selected = self._folder_tree.selection()
        if not selected:
            return
        iid = selected[0]
        path, current = self._folder_tree.item(iid, "values")
        new_val = "✗ Nej" if current == "✓ Ja" else "✓ Ja"
        self._folder_tree.item(iid, values=(path, new_val))
        self._autosave()

    def _on_tree_select(self, event) -> None:
        """Enable/disable action buttons based on treeview selection."""
        if self._folder_tree.selection():
            self._remove_btn.config(state="normal")
            self._recursive_btn.config(state="normal")
        else:
            self._remove_btn.config(state="disabled")
            self._recursive_btn.config(state="disabled")

    def _collect_config(self) -> dict:
        """Read all widget values and return config dict."""
        folders = []
        for iid in self._folder_tree.get_children():
            path, rec_label = self._folder_tree.item(iid, "values")
            folders.append({"path": path, "recursive": rec_label == "✓ Ja"})
        return {
            "scan_folders": folders,
            "file_age_days": self._age_var.get(),
            "scan_interval_minutes": FREQ_DISPLAY_TO_MINUTES[self._freq_var.get()],
            "file_types": [ext for ext, var in self._type_vars.items() if var.get()],
            "detection_types": [det_id for det_id, var in self._detection_vars.items() if var.get()],
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
