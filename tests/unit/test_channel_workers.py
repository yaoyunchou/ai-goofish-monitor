import asyncio
import threading

import pytest

from src.services.channel_workers import BUSY_MESSAGE, ChannelBusy, ChannelWorkers


def test_unknown_channel_is_rejected():
    workers = ChannelWorkers(("goofish", "xhs"))

    async def unused():
        return None

    with pytest.raises(ValueError, match="未知渠道"):
        workers.submit("douyin", unused, wait=True)


def test_goofish_waits_and_xhs_does_not():
    async def scenario():
        workers = ChannelWorkers(("goofish", "xhs"))
        workers.bind(asyncio.get_running_loop())
        release = asyncio.Event()
        xhs_started = asyncio.Event()
        order: list[str] = []

        async def first():
            order.append("g1")
            await release.wait()
            order.append("g1-done")

        async def second():
            order.append("g2")

        async def xhs_job():
            order.append("xhs")
            xhs_started.set()

        _status, first_done = workers.submit("goofish", first, wait=True)
        for _ in range(50):
            if order == ["g1"]:
                break
            await asyncio.sleep(0.01)
        assert order == ["g1"]

        status, second_done = workers.submit("goofish", second, wait=True)
        assert status == "queued"
        _xhs_status, xhs_done = workers.submit("xhs", xhs_job, wait=True)
        await asyncio.wait_for(xhs_started.wait(), timeout=1)
        assert "g2" not in order

        with pytest.raises(ChannelBusy, match=BUSY_MESSAGE):
            workers.submit("goofish", second, wait=False)

        release.set()
        await asyncio.wait_for(asyncio.wrap_future(first_done), timeout=1)
        await asyncio.wait_for(asyncio.wrap_future(second_done), timeout=1)
        await asyncio.wait_for(asyncio.wrap_future(xhs_done), timeout=1)
        assert order.index("xhs") < order.index("g2")
        assert order.index("g1-done") < order.index("g2")

    asyncio.run(scenario())


def test_xhs_manual_retry_does_not_overlap():
    async def scenario():
        workers = ChannelWorkers(("goofish", "xhs"))
        workers.bind(asyncio.get_running_loop())
        release = asyncio.Event()
        started = asyncio.Event()

        async def hold():
            started.set()
            await release.wait()

        workers.submit("xhs", hold, wait=False)
        await asyncio.wait_for(started.wait(), timeout=1)
        assert workers.is_busy("xhs") is True
        with pytest.raises(ChannelBusy):
            workers.submit("xhs", hold, wait=False)
        release.set()

    asyncio.run(scenario())


def test_xhs_thread_job_leaves_the_event_loop_free():
    async def scenario():
        workers = ChannelWorkers(("xhs",))
        loop = asyncio.get_running_loop()
        workers.bind(loop)
        started = asyncio.Event()
        release = threading.Event()
        ticks: list[str] = []

        def hold():
            loop.call_soon_threadsafe(started.set)
            release.wait(timeout=2)
            return "done"

        async def tick():
            ticks.append("tick")

        _status, done = workers.submit("xhs", hold, wait=False, on_thread=True)
        await asyncio.wait_for(started.wait(), timeout=1)
        await tick()
        assert ticks == ["tick"]
        assert workers.is_busy("xhs") is True
        release.set()
        assert await asyncio.wait_for(asyncio.wrap_future(done), timeout=1) == "done"

    asyncio.run(scenario())
