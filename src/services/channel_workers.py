"""按渠道排队执行。每个渠道一条线程，线程之间互不等待。"""
from __future__ import annotations

import asyncio
import queue
import threading
from concurrent.futures import Future
from typing import Awaitable, Callable, Union

BUSY_MESSAGE = "该渠道正在采集"
AsyncJob = Callable[[], Awaitable[object]]
SyncJob = Callable[[], object]
Job = Union[AsyncJob, SyncJob]


class ChannelBusy(Exception):
    def __init__(self, channel: str):
        self.channel = channel
        super().__init__(BUSY_MESSAGE)


class _Lane:
    def __init__(self) -> None:
        self.queue: queue.Queue[tuple[Job, Future, bool]] = queue.Queue()
        self.lock = threading.Lock()
        self.busy = False
        self.thread: threading.Thread | None = None


class ChannelWorkers:
    def __init__(self, channels: tuple[str, ...] = ("goofish", "xhs")) -> None:
        self._lanes = {name: _Lane() for name in channels}
        self._loop: asyncio.AbstractEventLoop | None = None
        self._bind_lock = threading.Lock()

    def bind(self, loop: asyncio.AbstractEventLoop) -> None:
        with self._bind_lock:
            self._loop = loop
            for name, lane in self._lanes.items():
                if lane.thread is not None and lane.thread.is_alive():
                    continue
                lane.thread = threading.Thread(
                    target=self._worker,
                    args=(name,),
                    name=f"channel-{name}",
                    daemon=True,
                )
                lane.thread.start()

    def submit(self, channel: str, job: Job, *, wait: bool, on_thread: bool = False) -> tuple[str, Future]:
        lane = self._lanes.get(channel)
        if lane is None:
            raise ValueError(f"未知渠道: {channel}")
        if self._loop is None:
            try:
                self.bind(asyncio.get_running_loop())
            except RuntimeError as exc:
                raise RuntimeError("渠道线程尚未绑定事件循环") from exc
        done: Future = Future()
        with lane.lock:
            if not wait and lane.busy:
                raise ChannelBusy(channel)
            status = "started" if not lane.busy else "queued"
            lane.queue.put((job, done, on_thread))
            lane.busy = True
        return status, done

    def is_busy(self, channel: str) -> bool:
        lane = self._lanes.get(channel)
        if lane is None:
            raise ValueError(f"未知渠道: {channel}")
        with lane.lock:
            return lane.busy

    def _worker(self, channel: str) -> None:
        lane = self._lanes[channel]
        while True:
            job, done, on_thread = lane.queue.get()
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
            except Exception as exc:
                print(f"[渠道 {channel}] 执行失败: {exc}")
                if not done.done():
                    done.set_exception(exc)
            finally:
                with lane.lock:
                    if lane.queue.empty():
                        lane.busy = False
                lane.queue.task_done()


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
