"""Blocking scheduler wrapping the backup job (cron or fixed interval)."""

from __future__ import annotations

import logging
from typing import Callable

from .config import Config

log = logging.getLogger(__name__)


def run_scheduler(cfg: Config, job: Callable[[], None]) -> None:
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.interval import IntervalTrigger

    scheduler = BlockingScheduler(timezone=cfg.timezone)

    if cfg.schedule_mode == "interval":
        trigger = IntervalTrigger(hours=cfg.schedule_interval_hours, timezone=cfg.timezone)
        log.info("scheduler: every %dh (tz=%s)", cfg.schedule_interval_hours, cfg.timezone)
    else:
        trigger = CronTrigger.from_crontab(cfg.schedule_cron, timezone=cfg.timezone)
        log.info("scheduler: cron '%s' (tz=%s)", cfg.schedule_cron, cfg.timezone)

    scheduler.add_job(job, trigger, id="backup", max_instances=1, coalesce=True)

    if cfg.run_on_startup:
        log.info("scheduler: RUN_ON_STARTUP — running one backup now")
        job()

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("scheduler: shutting down")
