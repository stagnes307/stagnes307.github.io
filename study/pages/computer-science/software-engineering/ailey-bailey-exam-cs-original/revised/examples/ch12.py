"""A timed-out waiter does not stop the running thread; a fence blocks publication."""
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import json
import threading


def main():
    started, release, finished = threading.Event(), threading.Event(), threading.Event()
    lock = threading.Lock()
    state = {'epoch': 1, 'status': 'RUNNING', 'final': 'old-success'}

    def work(epoch):
        started.set()
        if not release.wait(5):
            raise RuntimeError('test release missing')
        with lock:
            if state['epoch'] == epoch and state['status'] == 'RUNNING':
                state.update(status='SUCCEEDED', final='new-plan')
        finished.set()
        return 'calculated'

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(work, 1)
        assert started.wait(5)
        try:
            future.result(timeout=.01)
            raise AssertionError('expected timeout')
        except TimeoutError:
            pass
        assert not future.cancel()  # already running
        with lock:
            state.update(epoch=2, status='CANCELLED')
        release.set()
        assert future.result(timeout=5) == 'calculated'
        assert finished.is_set()
        assert state == {'epoch': 2, 'status': 'CANCELLED', 'final': 'old-success'}
    print(json.dumps({'waiter_timed_out': True, 'calculation_finished': True,
                      'cancelled_publication_blocked': True, 'previous_final_preserved': True}))


if __name__ == '__main__':
    main()
