"""渠道是队列，线程是有上限的池子。同渠道串行，没有任务时不养空闲线程。"""
from __future__ import annotations

import asyncio
import os
import threading
from collections import deque
from concurrent.futures import Future
from datetime import datetime
from pathlib import Path
from typing import Awaitable, Callable, Union

BUSY_MESSAGE = "该渠道正在采集"
MAX_RUNNING = 5
AsyncJob = Callable[[], Awaitable[object]]
SyncJob = Callable[[], object]
Job = Union[AsyncJob, SyncJob]


class ChannelBusy(Exception):
    def __init__(self, channel: str):
        self.channel = channel
        super().__init__(BUSY_MESSAGE)


class _Running:
    def __init__(self, thread: threading.Thread, future: Future) -> None:
        self.thread = thread
        self.future = future


class _Lane:
    def __init__(self) -> None:
        self.pending: deque[tuple[Job, Future, bool]] = deque()
        self.running: _Running | None = None


class ChannelWorkers:
    def __init__(self, channels: tuple[str, ...] = ("goofish", "xhs", "xhs_note")) -> None:
        self._lanes = {name: _Lane() for name in channels}
        self._loop: asyncio.AbstractEventLoop | None = None
        self._lock = threading.Lock()

    def bind(self, loop: asyncio.AbstractEventLoop) -> None:
        with self._lock:
            self._loop = loop

    def submit(self, channel: str, job: Job, *, wait: bool, on_thread: bool = False) -> tuple[str, Future]:
        self._recycle_dead()
        with self._lock:
            lane = self._require(channel)
            if self._loop is None:
                try:
                    self._loop = asyncio.get_running_loop()
                except RuntimeError as exc:
                    raise RuntimeError("渠道线程尚未绑定事件循环") from exc
            if not wait and (lane.running is not None or lane.pending):
                raise ChannelBusy(channel)
            if wait and lane.pending:
                self._log("queued", channel)
                return "queued", lane.pending[0][1]
            done: Future = Future()
            idle = lane.running is None and not lane.pending
            lane.pending.append((job, done, on_thread))
            room = self._running_count() < MAX_RUNNING
            status = "started" if idle and room else "queued"
            self._log("queued", channel)
            self._pump()
        return status, done

    def is_busy(self, channel: str) -> bool:
        self._recycle_dead()
        with self._lock:
            lane = self._require(channel)
            return lane.running is not None or bool(lane.pending)

    def _require(self, channel: str) -> _Lane:
        lane = self._lanes.get(channel)
        if lane is None:
            raise ValueError(f"未知渠道: {channel}")
        return lane

    def _running_count(self) -> int:
        return sum(1 for lane in self._lanes.values() if lane.running is not None)

    def _pump(self) -> None:
        while self._running_count() < MAX_RUNNING:
            started = False
            for name, lane in self._lanes.items():
                if lane.running is not None or not lane.pending:
                    continue
                if self._running_count() >= MAX_RUNNING:
                    break
                job, done, on_thread = lane.pending.popleft()
                thread = threading.Thread(
                    target=self._run_one,
                    args=(name, job, done, on_thread),
                    name=f"channel-{name}",
                    daemon=True,
                )
                lane.running = _Running(thread, done)
                thread.start()
                self._log("start", name)
                started = True
            if not started:
                break

    def _run_one(self, channel: str, job: Job, done: Future, on_thread: bool) -> None:
        lane = self._lanes[channel]
        try:
            if on_thread:
                result = job()
            else:
                loop = self._loop
                if loop is None:
                    raise RuntimeError("渠道线程尚未绑定事件循环")
                result = asyncio.run_coroutine_threadsafe(job(), loop).result()
            if not done.done():
                done.set_result(result)
            self._log("finish", channel)
        except Exception as exc:
            print(f"[渠道 {channel}] 执行失败: {exc}")
            if not done.done():
                done.set_exception(exc)
            self._log("fail", channel, str(exc))
        finally:
            with self._lock:
                if lane.running is not None and lane.running.future is done:
                    lane.running = None
                self._pump()

    def _recycle_dead(self) -> None:
        with self._lock:
            changed = False
            for name, lane in self._lanes.items():
                running = lane.running
                if running is None or running.thread.is_alive():
                    continue
                if not running.future.done():
                    running.future.set_exception(RuntimeError("渠道线程已退出"))
                lane.running = None
                self._log("recycle", name)
                changed = True
            if changed:
                self._pump()

    def _log(self, action: str, channel: str, detail: str = "") -> None:
        running = self._running_count()
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        extra = f" running={running}" if action == "queued" else ""
        if detail and action == "fail":
            extra = f" {detail.splitlines()[0][:180]}"
        line = f"{stamp} {channel} {action}{extra}\n"
        path = _log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line)


def _log_path() -> Path:
    override = os.environ.get("CHANNEL_WORKERS_LOG", "").strip()
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[2] / "logs" / "channel_workers.log"


_workers: ChannelWorkers | None = None


def get_channel_workers() -> ChannelWorkers:
    global _workers
    if _workers is None:
        _workers = ChannelWorkers()
    return _workers


async def launch_goofish(process_service, task_id: int, start: Callable[[], Awaitable[bool]], *, wait: bool) -> bool:
    """占用 goofish 直到子进程退出。wait=False 时在进程拉起后返回，渠道仍占用到退出。"""
    spawn_done: Future = Future()

    async def job() -> bool:
        try:
            started = bool(await start())
            if not spawn_done.done():
                spawn_done.set_result(started)
            if started:
                await process_service.wait_until_exit(task_id)
            return started
        except Exception as exc:
            if not spawn_done.done():
                spawn_done.set_exception(exc)
            raise

    _status, done = get_channel_workers().submit("goofish", job, wait=wait)
    if wait:
        return bool(await asyncio.wrap_future(done))
    return bool(await asyncio.wrap_future(spawn_done))
