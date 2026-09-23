"""Serialize device changes outside the match-state lock."""
from __future__ import annotations

import logging
from queue import Queue
from threading import Lock, Thread


class BackgroundJobs:
    def __init__(self, handler) -> None:
        self.handler = handler
        self.queue = Queue()
        self.start_lock = Lock()
        self.started = False

    def submit(self, job: dict) -> None:
        with self.start_lock:
            if not self.started:
                Thread(target=self._run, name="gateball-device-settings", daemon=True).start()
                self.started = True
        self.queue.put(job)

    def _run(self) -> None:
        while True:
            job = self.queue.get()
            try:
                self.handler(job)
            except Exception:
                logging.exception("Device settings job failed")
            finally:
                self.queue.task_done()
