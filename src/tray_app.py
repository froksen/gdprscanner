import queue
import logging

import pystray
from pystray import Icon, Menu, MenuItem

from src.config_store import ConfigStore
from src.events import OpenConfigEvent, ScanNowEvent, ShutdownEvent
from src.icon import create_icon_image


class TrayApp:
    """pystray Icon wrapper that runs on the main thread.

    Per D-01 and Pitfall 1, pystray must own the main thread on Windows.
    Callbacks post typed events to the shared queue; the UI thread polls
    that queue every 100 ms via root.after().
    """

    def __init__(self, event_queue: queue.Queue, config_store: ConfigStore) -> None:
        self.event_queue = event_queue
        self.config_store = config_store

        menu = Menu(
            MenuItem("Åbn indstillinger", self._on_open_config),
            MenuItem("Scan nu", self._on_scan_now),
            MenuItem("Afslut", self._on_quit),
        )

        self.icon = Icon(
            "GDPR Scanner",
            icon=create_icon_image(),
            title="GDPR Scanner",
            menu=menu,
        )

    # ------------------------------------------------------------------
    # Menu callbacks — called by pystray on its internal worker thread.
    # All communication back to the UI thread happens via the queue.
    # ------------------------------------------------------------------

    def _on_open_config(self) -> None:
        self.event_queue.put(OpenConfigEvent())

    def _on_scan_now(self) -> None:
        self.event_queue.put(ScanNowEvent())
        logging.info("Scan triggered")

    def _on_quit(self) -> None:
        self.event_queue.put(ShutdownEvent())
        self.icon.stop()

    # ------------------------------------------------------------------
    # Entry point — BLOCKS the calling thread (must be main thread).
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Start the pystray event loop.  This call blocks until the icon
        is stopped (i.e. until _on_quit calls self.icon.stop()).
        """
        self.icon.run(setup=self._on_ready)

    def _on_ready(self, icon: Icon) -> None:
        """Called by pystray once the tray icon is fully initialised."""
        icon.notify("GDPR Scanner kører i baggrunden", "GDPR Scanner")
