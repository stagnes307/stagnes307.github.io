"""Process memory versus thread memory. Run as a file (Windows spawn)."""
import json
import multiprocessing
import threading

STATE = {"count": 0}


def child(queue):
    STATE["count"] = 99
    queue.put(STATE["count"])


def thread_work():
    STATE["count"] += 1


def main():
    thread = threading.Thread(target=thread_work)
    thread.start()
    thread.join()
    after_thread = STATE["count"]
    ctx = multiprocessing.get_context("spawn")
    queue = ctx.Queue()
    process = ctx.Process(target=child, args=(queue,))
    process.start()
    try:
        child_count = queue.get(timeout=10)
        process.join(timeout=10)
        assert not process.is_alive(), "child did not exit"
        assert process.exitcode == 0
        assert (after_thread, child_count, STATE["count"]) == (1, 99, 1)
    finally:
        if process.is_alive():
            process.terminate()
            process.join()
        queue.close()
        queue.join_thread()
    print(json.dumps({"parent_after_thread": after_thread,
                      "child": child_count, "parent_after_process": STATE["count"]}))


if __name__ == "__main__":
    main()
