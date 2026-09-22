"""独立验证 APScheduler（与线上同款：Asia/Shanghai + CronTrigger）。

不启动 FastAPI / 不占 8010，不会跑真实采集。

  python scripts/verify_scheduler_timer.py --delay-seconds 300
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED, EVENT_JOB_MISSED
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.core.cron_utils import build_cron_trigger
from src.services.scheduler_service import DAILY_JOB_MISFIRE_GRACE_SECONDS

SHANGHAI = ZoneInfo("Asia/Shanghai")
JOB_ID = "timer_probe"


def _now() -> datetime:
    return datetime.now(SHANGHAI)


def main() -> int:
    parser = argparse.ArgumentParser(description="验证 APScheduler 能否在 N 秒后触发")
    parser.add_argument("--delay-seconds", type=int, default=300)
    parser.add_argument(
        "--grace-seconds",
        type=int,
        default=DAILY_JOB_MISFIRE_GRACE_SECONDS,
        help="misfire_grace_time；传 1 可复现旧默认",
    )
    args = parser.parse_args()
    return asyncio.run(_run(delay_seconds=args.delay_seconds, grace_seconds=args.grace_seconds))


async def _run(*, delay_seconds: int, grace_seconds: int) -> int:
    started = _now()
    target = started + timedelta(seconds=delay_seconds)
    cron = f"{target.second} {target.minute} {target.hour} * * *"
    events: list[dict] = []
    fired_at: list[datetime] = []

    def on_event(event) -> None:
        row = {
            "code": int(event.code),
            "job_id": getattr(event, "job_id", None),
            "scheduled_run_time": str(getattr(event, "scheduled_run_time", None)),
            "exception": str(getattr(event, "exception", None)),
            "wall": _now().isoformat(),
        }
        events.append(row)
        kind = {
            EVENT_JOB_MISSED: "MISSED",
            EVENT_JOB_ERROR: "ERROR",
            EVENT_JOB_EXECUTED: "EXECUTED",
        }.get(event.code, str(event.code))
        print(f"[{_now().strftime('%H:%M:%S')}] EVENT {kind} {row}", flush=True)

    async def probe_job() -> None:
        stamp = _now()
        fired_at.append(stamp)
        late = (stamp - target).total_seconds()
        print(
            f"[{stamp.strftime('%H:%M:%S')}] FIRED cron={cron} late={late:.2f}s",
            flush=True,
        )

    scheduler = AsyncIOScheduler(timezone=SHANGHAI)
    scheduler.add_listener(on_event, EVENT_JOB_MISSED | EVENT_JOB_ERROR | EVENT_JOB_EXECUTED)
    trigger = build_cron_trigger(cron, timezone=SHANGHAI)
    scheduler.add_job(
        probe_job,
        trigger=trigger,
        id=JOB_ID,
        name="timer probe",
        misfire_grace_time=grace_seconds,
        coalesce=True,
        max_instances=1,
        replace_existing=True,
    )
    scheduler.start()
    job = scheduler.get_job(JOB_ID)
    next_run = getattr(job, "next_run_time", None)
    print(
        json.dumps(
            {
                "started": started.isoformat(),
                "target": target.isoformat(),
                "cron": cron,
                "grace_seconds": grace_seconds,
                "next_run_time": next_run.isoformat() if next_run else None,
            },
            ensure_ascii=False,
            indent=2,
        ),
        flush=True,
    )

    deadline = delay_seconds + 20
    elapsed = 0
    while elapsed < deadline and not fired_at:
        await asyncio.sleep(5)
        elapsed += 5
        if elapsed % 30 == 0 and not fired_at:
            nxt = getattr(scheduler.get_job(JOB_ID), "next_run_time", None)
            print(
                f"[{_now().strftime('%H:%M:%S')}] waiting... {elapsed}s next_run={nxt}",
                flush=True,
            )

    await asyncio.sleep(1)
    if scheduler.running:
        scheduler.shutdown(wait=False)

    late = (fired_at[0] - target).total_seconds() if fired_at else None
    result = {
        "ok": bool(fired_at),
        "fired_at": fired_at[0].isoformat() if fired_at else None,
        "late_seconds": late,
        "events": events,
        "next_run_after": str(getattr(job, "next_run_time", None)),
    }
    out_dir = Path("logs")
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "scheduler-timer-probe.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    print(f"wrote {out_path}", flush=True)
    return 0 if fired_at else 1


if __name__ == "__main__":
    sys.exit(main())
