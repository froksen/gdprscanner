import threading
import queue
import logging

from src.config_store import ConfigStore
from src.events import ScanNowEvent


class ScanScheduler:
    """Periodic scan trigger running on a daemon thread.

    Uses threading.Event with a timeout loop (D-18) so the scheduler
    can be interrupted immediately on shutdown rather than waiting out
    a full sleep interval.

    Respects "Kun manuelt" mode (scan_interval_minutes == 0) by
    disabling the timed loop entirely (D-20).
    """

    def __init__(self, event_queue: queue.Queue, config_store: ConfigStore) -> None:
        self.event_queue = event_queue
        self.config_store = config_store
        self._stop_event = threading.Event()
        self._thread = None

    def start(self) -> None:
        """Start the scheduler daemon thread."""
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="ScanScheduler"
        )
        self._thread.start()

    def _run(self) -> None:
        interval = self.config_store.get_config().get("scan_interval_minutes", 1440)

        if interval == 0:
            # Manual-only mode — do not schedule automatic scans (D-20)
            logging.info("Scheduler disabled (manual only mode)")
            self._stop_event.wait()  # sleep until stop() wakes us
            return

        interval_seconds = interval * 60

        while not self._stop_event.is_set():
            # Wait up to interval_seconds; wake immediately if stop_event fires
            self._stop_event.wait(timeout=interval_seconds)
            if self._stop_event.is_set():
                break
            self._trigger_scan()

    def _trigger_scan(self) -> None:
        """Post a ScanNowEvent for the scheduled scan cycle."""
        self.event_queue.put(ScanNowEvent())
        logging.info("Scheduled scan triggered")

    def trigger_now(self) -> None:
        """Manually trigger a scan outside the normal schedule."""
        self.event_queue.put(ScanNowEvent())
        logging.info("Manual scan triggered")

    def stop(self) -> None:
        """Signal the scheduler to stop and wait for its thread to exit."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
