import queue
import threading
import logging
import tkinter as tk
import tkinter.ttk as ttk

from src.config_store import ConfigStore
from src.events import OpenConfigEvent, ScanNowEvent, ShutdownEvent
from src.config_dialog import ConfigDialog


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
