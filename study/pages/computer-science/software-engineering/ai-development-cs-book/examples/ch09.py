"""Concurrent coroutine waiting; no claim of CPU parallelism or speedup."""
import asyncio
import json
import os


async def main():
    started = asyncio.Queue()
    release = asyncio.Event()
    trace = []
    pids = set()

    async def work(name):
        pids.add(os.getpid())
        trace.append((name, "start"))
        await started.put(name)
        await release.wait()
        trace.append((name, "end"))
        return name

    tasks = [asyncio.create_task(work(name)) for name in ("A", "B")]
    names = [await started.get(), await started.get()]
    assert sorted(names) == ["A", "B"]
    assert all(stage == "start" for _, stage in trace)
    release.set()
    result = await asyncio.gather(*tasks)
    assert sorted(result) == ["A", "B"]
    assert len(pids) == 1
    print(json.dumps({"started_before_release": sorted(names),
                      "completed": sorted(result), "one_process": len(pids) == 1}))


if __name__ == "__main__":
    asyncio.run(asyncio.wait_for(main(), timeout=10))
