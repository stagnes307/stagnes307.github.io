"""Request deduplication and fenced publication inside one SQLite transaction."""
import json
import sqlite3


def main():
    db = sqlite3.connect(':memory:', isolation_level=None)
    db.executescript('''CREATE TABLE jobs(id INTEGER PRIMARY KEY, owner TEXT, key TEXT,
        body TEXT, epoch INTEGER, UNIQUE(owner,key));
        CREATE TABLE current(id INTEGER PRIMARY KEY, version INTEGER, epoch INTEGER, result TEXT, status TEXT);
        INSERT INTO current VALUES(1,2,3,'old-success','RUNNING');''')

    def accept(key, body):
        db.execute('INSERT OR IGNORE INTO jobs(owner,key,body,epoch) VALUES(?,?,?,?)', ('admin', key, body, 3))
        row = db.execute('SELECT id,body FROM jobs WHERE owner=? AND key=?', ('admin', key)).fetchone()
        if row[1] != body:
            raise ValueError('same key with different request')
        return row[0]

    def publish(version, epoch, result):
        db.execute('BEGIN IMMEDIATE')
        try:
            changed = db.execute("UPDATE current SET result=?,status='PUBLISHED' WHERE id=1 AND version=? AND epoch=? AND status='RUNNING'",
                                 (result, version, epoch)).rowcount
            db.execute('COMMIT')
            return changed
        except BaseException:
            db.execute('ROLLBACK')
            raise

    assert accept('K1', 'v2') == accept('K1', 'v2')
    try:
        accept('K1', 'v1')
        raise AssertionError('conflict accepted')
    except ValueError:
        pass
    assert publish(1, 3, 'stale-input') == 0
    assert publish(2, 2, 'stale-worker') == 0
    assert db.execute('SELECT result FROM current').fetchone()[0] == 'old-success'
    assert publish(2, 3, 'validated-candidate') == 1
    assert publish(2, 3, 'second-publication') == 0
    assert db.execute('SELECT result FROM current').fetchone()[0] == 'validated-candidate'
    assert db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0] == 1
    db.close()
    print(json.dumps({'job_rows': 1, 'stale_input_rows': 0, 'stale_worker_rows': 0,
                      'accepted_rows': 1, 'repeat_publication_rows': 0, 'external_effects_tested': False}))


if __name__ == '__main__':
    main()
