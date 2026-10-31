"""Seven tiny fictional CSVs; reduced columns, not the actual exam dataset."""
import csv
import hashlib
import io
import json

DATA = {
    "sites": "site_id\nICN\n",
    "shifts": "shift_code,site_id\nA,ICN\n",
    "employees": "emp_id,site_id,shift_code\nE1,ICN,A\n",
    "work_schedule": "date,emp_id,status\n2026-07-20,E1,WORK\n",
    "stops": 'stop_id,name\nS1,"중앙, 정류장"\n',
    "travel_times": "from_id,to_id,minutes\nS1,ICN,12\n",
    "ridership": "date,stop_id,boardings\n2026-07-20,S1,1\n",
}
REQUIRED = {name: set(next(csv.reader(io.StringIO(text)))) for name, text in DATA.items()}


def validate(files):
    if set(files) != set(REQUIRED):
        raise ValueError("exactly seven named CSVs required")
    tables = {}
    for name, text in files.items():
        reader = csv.DictReader(io.StringIO(text))
        if len(reader.fieldnames or []) != len(set(reader.fieldnames or [])) or not REQUIRED[name] <= set(reader.fieldnames or []):
            raise ValueError(name + ": header")
        rows = list(reader)
        if any(None in row or any(value is None or not value.strip() for value in row.values()) for row in rows):
            raise ValueError(name + ": empty/extra cells")
        tables[name] = rows
    sites = {r["site_id"] for r in tables["sites"]}
    shifts = {r["shift_code"]: r["site_id"] for r in tables["shifts"]}
    employees = {r["emp_id"]: r for r in tables["employees"]}
    if len(employees) != len(tables["employees"]):
        raise ValueError("employees: duplicate")
    for row in employees.values():
        if row["site_id"] not in sites or shifts.get(row["shift_code"]) != row["site_id"]:
            raise ValueError("employees: reference")
    for row in tables["work_schedule"]:
        if row["emp_id"] not in employees or row["status"] not in {"WORK", "OFF"}:
            raise ValueError("work_schedule: reference/status")
    nodes = sites | {r["stop_id"] for r in tables["stops"]}
    for row in tables["travel_times"]:
        if row["from_id"] not in nodes or row["to_id"] not in nodes or int(row["minutes"]) <= 0:
            raise ValueError("travel_times: reference/minutes")
    return tables


def fingerprint(files):
    return hashlib.sha256(json.dumps(files, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def apply(state, files, expected_hash):
    snapshot = dict(files)
    tables = validate(snapshot)  # no state mutation before validation succeeds
    if fingerprint(snapshot) != expected_hash:
        raise ValueError("validated input changed")
    state.update(input_hash=expected_hash, tables=tables)
    # This in-memory demonstration preserves the prior plan; production uses a transaction.


def main():
    snapshot = dict(DATA)  # strings are immutable; keep this exact input for use.
    validated = validate(snapshot)
    state = {"input_hash": fingerprint(snapshot), "plan": "previous-success"}
    apply(state, snapshot, fingerprint(snapshot))
    before = dict(state)
    broken = dict(snapshot)
    broken["work_schedule"] = broken["work_schedule"].replace("E1", "UNKNOWN")
    try:
        apply(state, broken, fingerprint(broken))
        raise AssertionError("invalid input accepted")
    except ValueError:
        pass
    assert state == before
    changed = dict(snapshot)
    changed["stops"] = changed["stops"].replace("중앙", "서쪽")
    try:
        apply(state, changed, fingerprint(snapshot))
        raise AssertionError("changed snapshot accepted")
    except ValueError:
        pass
    assert state == before
    assert validated["stops"][0]["name"] == "중앙, 정류장"
    print(json.dumps({"csv_count": len(snapshot), "quoted_comma": True,
                      "invalid_reference_rejected": True, "changed_input_rejected": True,
                      "old_state_preserved": state == before}))


if __name__ == "__main__":
    main()
