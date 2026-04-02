import queue
import logging
import sys

from src.config_store import ConfigStore
from src.ui_thread import UIThread
from src.scheduler import ScanScheduler
from src.tray_app import TrayApp


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(threadName)s] %(levelname)s: %(message)s",
    )
    logging.info("GDPR Scanner starting")

    event_queue = queue.Queue()
    config_store = ConfigStore()

    # Start UI thread (daemon) — tkinter mainloop on worker thread (D-02, Pitfall 1 & 2)
    ui_thread = UIThread(event_queue, config_store)
    ui_thread.start()

    # Start scheduler thread (daemon) — reads scan_interval_minutes from config
    scheduler = ScanScheduler(event_queue, config_store)
    scheduler.start()

    # Run tray app on main thread — BLOCKS until user clicks Afslut (D-01)
    # pystray requires main-thread ownership on Windows (Pitfall 1)
    tray = TrayApp(event_queue, config_store)
    logging.info("Tray icon starting on main thread")
    tray.run()

    # tray.run() returns after icon.stop() is called (from _on_quit callback)
    logging.info("Tray stopped, shutting down")
    scheduler.stop()
    sys.exit(0)


if __name__ == "__main__":
    main()
