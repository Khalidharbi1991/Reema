"""Lanes, timeouts, one retry, and the heartbeat.

Two lanes run side by side, so a long background job never holds up chat:
  chat        replies, approvals and Undo
  background  later steps' long jobs (empty in step 2)
Each job has a time limit. A failure that may pass (busy service, timeout) is retried once
after a short wait; the second failure is final, and for chat Ahmad says so plainly.
"""

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as JobTimeout
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, Optional

from . import VERSION
from .engine import Engine, JobError
from .store import StoreError

log = logging.getLogger("snafi_worker")


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def run_job(store, engine: Engine, job: Dict, timeout: float, retry_delay: float,
            now: Callable[[], datetime] = lambda: datetime.now(timezone.utc)) -> str:
    """Run one claimed job; return its final status: done, queued (retry) or failed."""
    pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix=f"job-{job['id'][:8]}")
    future = pool.submit(engine.handle, job)
    try:
        result = future.result(timeout=timeout)
        store.update("jobs", job["id"], {"status": "done", "result": result, "error": None, "finished_at": _iso(now())})
        log.info("job done id=%s kind=%s", job["id"], job["kind"])
        return "done"
    except JobTimeout:
        error, retryable = f"timed out after {int(timeout)}s", True
    except (JobError, StoreError) as exc:
        error, retryable = str(exc)[:300], exc.retryable
    except Exception as exc:  # unexpected: never retried blindly, never crashes the lane
        error, retryable = f"unexpected {type(exc).__name__}", False
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    if retryable and job.get("attempts", 1) < job.get("max_attempts", 2):
        store.update("jobs", job["id"], {"status": "queued", "error": error,
                                         "run_after": _iso(now() + timedelta(seconds=retry_delay))})
        log.warning("job retry id=%s kind=%s reason=%s", job["id"], job["kind"], error)
        return "queued"
    store.update("jobs", job["id"], {"status": "failed", "error": error, "finished_at": _iso(now())})
    log.error("job failed id=%s kind=%s reason=%s", job["id"], job["kind"], error)
    try:
        engine.apologise(job)
    except Exception:  # the apology is a courtesy; the failure is already recorded
        pass
    return "failed"


class Lane(threading.Thread):
    def __init__(self, name, settings, store, engine, worker_id, stop: threading.Event):
        super().__init__(name=f"lane-{name}", daemon=True)
        self.lane, self.settings, self.store, self.engine = name, settings, store, engine
        self.worker_id, self.stop = worker_id, stop
        self.last_job_at: Optional[str] = None
        self.last_error: Optional[str] = None

    def step(self) -> Optional[str]:
        job = self.store.claim_job(self.lane, self.worker_id)
        if not job:
            return None
        self.last_job_at = _iso(datetime.now(timezone.utc))
        return run_job(self.store, self.engine, job, self.settings.timeout_seconds, self.settings.retry_delay_seconds)

    def run(self):
        while not self.stop.is_set():
            try:
                outcome = self.step()
                self.last_error = None
            except Exception as exc:  # database unreachable: wait and try again
                outcome, self.last_error = None, type(exc).__name__
                log.warning("lane %s waiting: %s", self.lane, self.last_error)
            if outcome is None:
                self.stop.wait(self.settings.poll_seconds)


def heartbeat_row(owner_id: str, worker_id: str, lanes: Dict[str, Lane], now: datetime) -> Dict:
    return {
        "user_id": owner_id, "worker_id": worker_id, "version": VERSION, "last_seen": _iso(now),
        "updated_at": _iso(now),
        "lanes": {name: {"alive": lane.is_alive(), "last_job_at": lane.last_job_at, "error": lane.last_error}
                  for name, lane in lanes.items()},
    }


class Heartbeat(threading.Thread):
    def __init__(self, store, owner_id, worker_id, lanes, seconds, stop: threading.Event):
        super().__init__(name="heartbeat", daemon=True)
        self.store, self.owner_id, self.worker_id = store, owner_id, worker_id
        self.lanes, self.seconds, self.stop = lanes, seconds, stop

    def beat(self, now: Optional[datetime] = None):
        self.store.upsert("worker_status", heartbeat_row(self.owner_id, self.worker_id, self.lanes,
                                                         now or datetime.now(timezone.utc)), "user_id")

    def run(self):
        while not self.stop.is_set():
            try:
                self.beat()
            except Exception as exc:
                log.warning("heartbeat failed: %s", type(exc).__name__)
            self.stop.wait(self.seconds)


def sleep_forever(stop: threading.Event):
    while not stop.is_set():
        time.sleep(1)
