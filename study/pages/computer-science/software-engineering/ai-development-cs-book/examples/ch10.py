"""Persistent claim + real spawned worker. Fictional miniature queue, no lease recovery."""
import json
import multiprocessing as mp
import os
import sqlite3
import tempfile
from pathlib import Path


def claim(path):
    db = sqlite3.connect(path, isolation_level=None, timeout=5)
    try:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute("SELECT id FROM jobs WHERE status='QUEUED' ORDER BY id LIMIT 1").fetchone()
        if not row:
            db.execute('COMMIT')
            return None
        assert db.execute("UPDATE jobs SET status='RUNNING' WHERE id=? AND status='QUEUED'", row).rowcount == 1
        db.execute('COMMIT')
        return row[0]
    finally:
        db.close()


def worker(path):
    job = claim(path)
    if job is None:
        return
    db = sqlite3.connect(path)
    try:
        with db:
            db.execute("UPDATE jobs SET status='SUCCEEDED', result=?, pid=? WHERE id=? AND status='RUNNING'",
                       ('fictional-plan', os.getpid(), job))
    finally:
        db.close()


def main():
    with tempfile.TemporaryDirectory() as temp:
        path = str(Path(temp) / 'jobs.db')
        db = sqlite3.connect(path)
        db.execute('CREATE TABLE jobs(id INTEGER PRIMARY KEY, status TEXT, result TEXT, pid INTEGER)')
        db.execute("INSERT INTO jobs VALUES(1,'QUEUED',NULL,NULL)")
        db.commit()
        db.close()
        processes = [mp.get_context('spawn').Process(target=worker, args=(path,)) for _ in range(2)]
        try:
            for p in processes:
                p.start()
            for p in processes:
                p.join(15)
                assert p.exitcode == 0
            db = sqlite3.connect(path)
            try:
                status, result, pid = db.execute('SELECT status,result,pid FROM jobs').fetchone()
                assert (status, result) == ('SUCCEEDED', 'fictional-plan')
                assert pid != os.getpid()
                assert claim(path) is None
            finally:
                db.close()
        finally:
            for p in processes:
                if p.is_alive():
                    p.terminate()
                    p.join()
    print(json.dumps({'workers': 2, 'final_rows': 1, 'separate_pid': True,
                      'recovery_after_claim_tested': False}))


if __name__ == '__main__':
    main()
