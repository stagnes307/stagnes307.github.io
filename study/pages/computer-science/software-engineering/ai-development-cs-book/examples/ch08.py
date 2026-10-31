"""Rollback, file persistence and optimistic version check, sequentially exercised."""
import json
import sqlite3
import tempfile
from pathlib import Path


def main():
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / "sample.db"
        db = sqlite3.connect(path, isolation_level=None)
        db.execute("PRAGMA foreign_keys=ON")
        assert db.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        db.executescript("""
          CREATE TABLE input(id INTEGER PRIMARY KEY, version INTEGER NOT NULL);
          CREATE TABLE plan(id INTEGER PRIMARY KEY, input_id INTEGER REFERENCES input(id));
          INSERT INTO input VALUES(1,1);
        """)
        db.execute("BEGIN IMMEDIATE")
        try:
            db.execute("INSERT INTO plan VALUES(1,1)")
            db.execute("INSERT INTO plan VALUES(2,999)")
            raise AssertionError("foreign key accepted")
        except sqlite3.IntegrityError:
            db.execute("ROLLBACK")
        assert db.execute("SELECT COUNT(*) FROM plan").fetchone()[0] == 0
        first = db.execute("UPDATE input SET version=2 WHERE id=1 AND version=1").rowcount
        stale = db.execute("UPDATE input SET version=3 WHERE id=1 AND version=1").rowcount
        assert (first, stale) == (1, 0)
        db.close()
        reopened = sqlite3.connect(path)
        try:
            assert reopened.execute("SELECT version FROM input WHERE id=1").fetchone()[0] == 2
        finally:
            reopened.close()
    print(json.dumps({"rollback_rows": 0, "accepted_update": first,
                      "stale_update": stale, "reopened_version": 2,
                      "simultaneous_writers_tested": False}))


if __name__ == "__main__":
    main()
