"""Four-question miniature lab: Python 3.11+, standard library, no service needed.

Run from study: python cs-theory-book/edition-2/examples/four_questions.py
Each run uses a temporary SQLite file and removes it afterwards; JSON is evidence
for this miniature only, never evidence about the learner's exam submission.

SCHEMA is a teaching schema, not the unavailable exam CSV schema. Seven CSVs are
stored together as one immutable bundle_json snapshot, not seven production SQL
tables. Application checks cover the rules implemented in validate_input; SQLite
foreign keys alone do not guarantee full assignments or correct timetables.

create_plan is a fixed-path, one-day, one-site, one-shift toy generator. It batches
people to capacity; it does not optimize routes. validate_plan independently reads
the frozen inputs, never a Creator success flag. It checks tuple multiplicities,
candidate stops, directional edges, leg times, per-segment loads and work dates.
The JSON string validated is the string committed and exported; no mutable object
is shared after validation. Creator/Validator run outside write transactions.

Real HTTP, auth/login, Docker, queues, Worker processes, forced termination,
deadline/cancel delivery, multi-server recovery and performance are NOT implemented
or tested. Reconnect/recovery below simulates a dead single execution process by
leaving RUNNING in a file DB. It does not kill a running process. Startup recovery
is valid only after exclusive ownership/no previous execution has been established.
"""

from collections import Counter
from copy import deepcopy
from datetime import date, datetime, time, timedelta, timezone
import csv
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import tempfile


SCHEMA = {
    'sites': ('site_id', 'name'),
    'shifts': ('shift_id', 'site_id', 'start_time', 'end_time'),
    'employees': ('employee_id', 'site_id', 'stop_id', 'name'),
    'work_schedule': ('employee_id', 'work_date', 'shift_id', 'status'),
    'stops': ('stop_id', 'name', 'candidate'),
    'travel_times': ('direction', 'from_id', 'to_id', 'minutes'),
    'ridership': ('employee_id', 'rate'),
}
DEFAULT_SETTINGS = {'capacity': 45, 'arrival_buffer': 20, 'work_date': '2026-11-02'}
KST = timezone(timedelta(hours=9))


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def example_bundle():
    """All seven tables are present; historical rate 0 does not remove E02."""
    return {
        'sites': 'site_id,name\nS1,공장\n',
        'shifts': 'shift_id,site_id,start_time,end_time\nN,S1,00:10,08:10\n',
        'employees': 'employee_id,site_id,stop_id,name\nE01,S1,A,가\nE02,S1,B,나\nE03,S1,A,다\n',
        'work_schedule': 'employee_id,work_date,shift_id,status\nE01,2026-11-02,N,WORK\nE02,2026-11-02,N,WORK\nE03,2026-11-02,N,OFF\n',
        'stops': 'stop_id,name,candidate\nA,정류장A,1\nB,정류장B,1\n',
        'travel_times': 'direction,from_id,to_id,minutes\nIN,A,B,5\nIN,B,S1,10\nOUT,S1,B,12\nOUT,B,A,6\n',
        'ridership': 'employee_id,rate\nE01,1\nE02,0\nE03,0.5\n',
    }


def freeze_bundle(bundle):
    """Return text and hash; validate/apply use this same immutable text."""
    text = canonical(bundle)
    return text, sha(text)


def validate_input(bundle_text):
    """Strict teaching headers, keys, value types and references; raise on error.

    Does NOT prove every feasible path exists or all exam business rules. Travel
    completeness is checked for the actual candidate by validate_plan. Ridership
    headers/file are required; rows may be empty (history is optional in this
    teaching schema). Missing history never removes a WORK person from targets.
    """
    bundle = json.loads(bundle_text)
    if set(bundle) != set(SCHEMA):
        raise ValueError('seven-files')
    tables = {}
    for name, columns in SCHEMA.items():
        reader = csv.DictReader(io.StringIO(bundle[name]))
        if reader.fieldnames != list(columns):
            raise ValueError('headers:' + name)
        rows = list(reader)
        if any(set(row) != set(columns) or any(v is None or not v.strip() for v in row.values())
               for row in rows):
            raise ValueError('cells:' + name)
        tables[name] = rows
    keys = {
        'sites': ('site_id',), 'shifts': ('shift_id',),
        'employees': ('employee_id',), 'stops': ('stop_id',),
        'work_schedule': ('employee_id', 'work_date'),
        'travel_times': ('direction', 'from_id', 'to_id'),
        'ridership': ('employee_id',),
    }
    for name, columns in keys.items():
        values = [tuple(row[c] for c in columns) for row in tables[name]]
        if len(values) != len(set(values)):
            raise ValueError('duplicate-key:' + name)
    sites = {r['site_id'] for r in tables['sites']}
    stops = {r['stop_id'] for r in tables['stops']}
    if sites & stops:
        raise ValueError('node-id-collision')
    employees = {r['employee_id']: r for r in tables['employees']}
    shifts = {r['shift_id']: r for r in tables['shifts']}
    for row in tables['stops']:
        if row['candidate'] not in ('0', '1'):
            raise ValueError('candidate-enum')
    for row in shifts.values():
        if row['site_id'] not in sites:
            raise ValueError('shift-site-reference')
        time.fromisoformat(row['start_time'])
        time.fromisoformat(row['end_time'])
    for row in employees.values():
        if row['site_id'] not in sites or row['stop_id'] not in stops:
            raise ValueError('employee-reference')
    for row in tables['work_schedule']:
        date.fromisoformat(row['work_date'])
        if row['status'] not in ('WORK', 'OFF'):
            raise ValueError('work-status')
        if row['employee_id'] not in employees or row['shift_id'] not in shifts:
            raise ValueError('schedule-reference')
        if employees[row['employee_id']]['site_id'] != shifts[row['shift_id']]['site_id']:
            raise ValueError('schedule-site')
    for row in tables['travel_times']:
        if row['direction'] not in ('IN', 'OUT') or int(row['minutes']) <= 0:
            raise ValueError('travel-value')
        if row['from_id'] not in sites | stops or row['to_id'] not in sites | stops:
            raise ValueError('travel-reference')
    for row in tables['ridership']:
        if row['employee_id'] not in employees or not 0 <= float(row['rate']) <= 1:
            raise ValueError('ridership-value')
    return tables


def shift_bounds(schedule, shifts):
    row = shifts[schedule['shift_id']]
    start = datetime.combine(date.fromisoformat(schedule['work_date']), time.fromisoformat(row['start_time']), KST)
    end = datetime.combine(start.date(), time.fromisoformat(row['end_time']), KST)
    if end <= start:
        end += timedelta(days=1)
    return start, end


def create_plan(tables, settings):
    """Fixed A-B-S1 route; input path/shift optimization is out of scope."""
    workers = [r for r in tables['work_schedule']
               if r['work_date'] == settings['work_date'] and r['status'] == 'WORK']
    shifts = {r['shift_id']: r for r in tables['shifts']}
    employees = {r['employee_id']: r for r in tables['employees']}
    if settings['capacity'] < 1 or len({r['shift_id'] for r in workers}) != 1:
        raise ValueError('toy-generator-one-shift-positive-capacity')
    start, end = shift_bounds(workers[0], shifts)
    inbound = start - timedelta(minutes=settings['arrival_buffer'])
    outbound = end + timedelta(minutes=10)
    trips = []
    for offset in range(0, len(workers), settings['capacity']):
        batch = workers[offset:offset + settings['capacity']]
        for direction, path, times in (
            ('IN', ['A', 'B', 'S1'], [inbound - timedelta(minutes=15), inbound - timedelta(minutes=10), inbound]),
            ('OUT', ['S1', 'B', 'A'], [outbound, outbound + timedelta(minutes=12), outbound + timedelta(minutes=18)]),
        ):
            trips.append({
                'work_date': settings['work_date'], 'direction': direction,
                'path': path, 'times': [t.isoformat(timespec='minutes') for t in times],
                'assignments': [{'employee_id': r['employee_id'],
                                 'board': employees[r['employee_id']]['stop_id'] if direction == 'IN' else 'S1',
                                 'alight': 'S1' if direction == 'IN' else employees[r['employee_id']]['stop_id']}
                                for r in batch],
            })
    return trips


def validate_plan(tables, settings, plan_text):
    """Independent rule checker; returns errors and observed segment loads.

    This checks a documented candidate structure, not arbitrary hostile JSON.
    JSON type/schema rejection would be an additional API boundary in a service.
    """
    plan = json.loads(plan_text)
    expected_rows = [r for r in tables['work_schedule']
                     if r['work_date'] == settings['work_date'] and r['status'] == 'WORK']
    expected = Counter((r['employee_id'], r['work_date'], d) for r in expected_rows for d in ('IN', 'OUT'))
    actual = Counter((a['employee_id'], trip['work_date'], trip['direction'])
                     for trip in plan for a in trip['assignments'])
    errors = [] if actual == expected else ['coverage']
    employees = {r['employee_id']: r for r in tables['employees']}
    schedules = {(r['employee_id'], r['work_date']): r for r in expected_rows}
    shifts = {r['shift_id']: r for r in tables['shifts']}
    candidate = {r['stop_id'] for r in tables['stops'] if r['candidate'] == '1'}
    sites = {r['site_id'] for r in tables['sites']}
    travel = {(r['direction'], r['from_id'], r['to_id']): int(r['minutes']) for r in tables['travel_times']}
    loads = []
    for trip in plan:
        direction, path = trip['direction'], trip['path']
        moments = [datetime.fromisoformat(t) for t in trip['times']]
        if (direction not in ('IN', 'OUT') or len(path) < 2 or len(path) != len(set(path))
                or len(path) != len(moments) or any(t.tzinfo is None for t in moments)):
            errors.append('trip-schema')
            continue
        if any(node not in candidate | sites for node in path):
            errors.append('candidate-stop')
        segment_loads = [0] * (len(path) - 1)
        for index, (left, right) in enumerate(zip(path, path[1:])):
            minutes = travel.get((direction, left, right))
            if minutes is None:
                errors.append('directional-edge')
            elif moments[index + 1] - moments[index] != timedelta(minutes=minutes):
                errors.append('travel-time')
        for assignment in trip['assignments']:
            employee = employees.get(assignment['employee_id'])
            schedule = schedules.get((assignment['employee_id'], trip['work_date']))
            if employee is None or schedule is None:
                errors.append('unexpected-person-date')
                continue
            correct_board = employee['stop_id'] if direction == 'IN' else employee['site_id']
            correct_alight = employee['site_id'] if direction == 'IN' else employee['stop_id']
            if (assignment['board'] != correct_board or assignment['alight'] != correct_alight
                    or assignment['board'] not in path or assignment['alight'] not in path):
                errors.append('boarding')
                continue
            board, alight = path.index(assignment['board']), path.index(assignment['alight'])
            if board >= alight:
                errors.append('boarding-order')
                continue
            for index in range(board, alight):
                segment_loads[index] += 1
            start, end = shift_bounds(schedule, shifts)
            if direction == 'IN' and moments[alight] > start - timedelta(minutes=settings['arrival_buffer']):
                errors.append('arrival')
            if direction == 'OUT' and moments[board] < end + timedelta(minutes=10):
                errors.append('departure')
        if any(n > settings['capacity'] for n in segment_loads):
            errors.append('capacity')
        loads.append({'direction': direction, 'loads': segment_loads})
    return {'errors': sorted(set(errors)), 'candidate_sha256': sha(plan_text),
            'input_rows_sha256': sha(canonical(tables)), 'settings_sha256': sha(canonical(settings)),
            'segment_loads': loads}


def connect(path):
    db = sqlite3.connect(path, isolation_level=None)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    db.executescript('''
        CREATE TABLE IF NOT EXISTS datasets(version INTEGER PRIMARY KEY, digest TEXT NOT NULL, rows_digest TEXT NOT NULL, bundle_json TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS state(id INTEGER PRIMARY KEY CHECK(id=1), data_version INTEGER REFERENCES datasets(version), settings_version INTEGER NOT NULL, settings_json TEXT NOT NULL, final_id INTEGER);
        CREATE TABLE IF NOT EXISTS jobs(id INTEGER PRIMARY KEY, request_key TEXT UNIQUE NOT NULL, data_version INTEGER NOT NULL REFERENCES datasets(version), settings_version INTEGER NOT NULL, settings_json TEXT NOT NULL, status TEXT NOT NULL, report_json TEXT);
        CREATE TABLE IF NOT EXISTS finals(id INTEGER PRIMARY KEY, job_id INTEGER UNIQUE NOT NULL REFERENCES jobs(id), data_version INTEGER NOT NULL, settings_version INTEGER NOT NULL, plan_json TEXT NOT NULL, digest TEXT NOT NULL);
    ''')
    db.execute('INSERT OR IGNORE INTO state VALUES(1,NULL,1,?,NULL)', (canonical(DEFAULT_SETTINGS),))
    return db


def apply_dataset(db, bundle_text, checked_digest, inject_failure=False):
    tables = validate_input(bundle_text)  # Outside write transaction, same immutable text.
    rows_digest = sha(canonical(tables))
    if sha(bundle_text) != checked_digest:
        raise ValueError('checked-input-changed')
    db.execute('BEGIN IMMEDIATE')
    try:
        cursor = db.execute('INSERT INTO datasets(digest,rows_digest,bundle_json) VALUES(?,?,?)', (checked_digest, rows_digest, bundle_text))
        if inject_failure:
            raise RuntimeError('injected-after-snapshot-before-pointer')
        db.execute('UPDATE state SET data_version=? WHERE id=1', (cursor.lastrowid,))
        db.commit()
        return cursor.lastrowid
    except BaseException:
        db.rollback()  # Does not claim rollback of memory/files/queues.
        raise


def change_settings(db, **changes):
    state = db.execute('SELECT * FROM state').fetchone()
    settings = json.loads(state['settings_json']) | changes
    if not isinstance(settings['capacity'], int) or settings['capacity'] < 1 or settings['arrival_buffer'] < 0:
        raise ValueError('settings')
    date.fromisoformat(settings['work_date'])
    db.execute('UPDATE state SET settings_version=settings_version+1,settings_json=? WHERE id=1', (canonical(settings),))


def start_job(db, request_key):
    state = db.execute('SELECT * FROM state').fetchone()
    existing = db.execute('SELECT * FROM jobs WHERE request_key=?', (request_key,)).fetchone()
    if existing:
        if (existing['data_version'], existing['settings_version']) != (state['data_version'], state['settings_version']):
            raise ValueError('idempotency-key-reused-for-different-input')
        return existing['id']
    if state['data_version'] is None:
        raise ValueError('no-applied-input')
    result = db.execute('INSERT INTO jobs(request_key,data_version,settings_version,settings_json,status) VALUES(?,?,?,?,?)',
                        (request_key, state['data_version'], state['settings_version'], state['settings_json'], 'RUNNING'))
    return result.lastrowid


def prepare(db, job_id):
    """Snapshot load then pure computation; no open write transaction."""
    job = db.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone()
    text = db.execute('SELECT bundle_json FROM datasets WHERE version=?', (job['data_version'],)).fetchone()[0]
    tables, settings = validate_input(text), json.loads(job['settings_json'])
    assert not db.in_transaction
    plan_text = canonical(create_plan(tables, settings))
    report = validate_plan(tables, settings, plan_text)
    return plan_text, report


def fail_job(db, job_id, report):
    db.execute("UPDATE jobs SET status='INVALID',report_json=? WHERE id=? AND status='RUNNING'", (canonical(report), job_id))


def publish(db, job_id, plan_text, report):
    """Single short commit; exact checked JSON, versions, live job all required.

    report is trusted internal Validator output; this is not a public endpoint that
    accepts client-provided reports. No distributed attempt/lease is implemented.
    """
    if report['errors'] or sha(plan_text) != report['candidate_sha256']:
        raise ValueError('unvalidated-or-changed-plan')
    db.execute('BEGIN IMMEDIATE')
    try:
        job = db.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone()
        state = db.execute('SELECT * FROM state').fetchone()
        input_digest = db.execute('SELECT rows_digest FROM datasets WHERE version=?', (job['data_version'],)).fetchone()[0]
        if (job['status'] != 'RUNNING' or job['data_version'] != state['data_version']
                or job['settings_version'] != state['settings_version']
                or input_digest != report['input_rows_sha256']
                or sha(job['settings_json']) != report['settings_sha256']):
            raise ValueError('stale-input-settings-or-job')
        result = db.execute('INSERT INTO finals(job_id,data_version,settings_version,plan_json,digest) VALUES(?,?,?,?,?)',
                            (job_id, job['data_version'], job['settings_version'], plan_text, report['candidate_sha256']))
        db.execute('UPDATE state SET final_id=? WHERE id=1', (result.lastrowid,))
        db.execute("UPDATE jobs SET status='SUCCEEDED',report_json=? WHERE id=?", (canonical(report), job_id))
        db.commit()
    except BaseException:
        db.rollback()
        raise


def export_plan(db, job_id):
    """Lookup by job ID after response loss, also allows historical lookup."""
    row = db.execute('SELECT * FROM finals WHERE job_id=?', (job_id,)).fetchone()
    if row is None:
        return None
    assert sha(row['plan_json']) == row['digest']
    state = db.execute('SELECT * FROM state').fetchone()
    return {'job_id': job_id, 'data_version': row['data_version'], 'settings_version': row['settings_version'],
            'current': (row['id'] == state['final_id']
                        and (row['data_version'], row['settings_version']) == (state['data_version'], state['settings_version'])),
            'plan_json': row['plan_json'], 'sha256': row['digest']}


def recover_single_process(db):
    """Startup-only policy after proving exclusive single-process ownership."""
    return db.execute("UPDATE jobs SET status='INTERRUPTED' WHERE status='RUNNING'").rowcount


def expect_error(action, kind=ValueError):
    try:
        action()
    except kind:
        return
    raise AssertionError('Expected ' + kind.__name__)


def many_workers(bundle, number):
    bundle = deepcopy(bundle)
    bundle['employees'] = 'employee_id,site_id,stop_id,name\n' + ''.join(f'E{i:02},S1,A,사람{i}\n' for i in range(1, number + 1))
    bundle['work_schedule'] = 'employee_id,work_date,shift_id,status\n' + ''.join(f'E{i:02},2026-11-02,N,WORK\n' for i in range(1, number + 1))
    bundle['ridership'] = 'employee_id,rate\n' + ''.join(f'E{i:02},0\n' for i in range(1, number + 1))
    return bundle


def main():
    bundle = example_bundle()
    text, digest = freeze_bundle(bundle)
    tables = validate_input(text)
    settings = deepcopy(DEFAULT_SETTINGS)
    good = create_plan(tables, settings)
    good_text = canonical(good)
    report = validate_plan(tables, settings, good_text)
    assert report['errors'] == []
    assert report['segment_loads'] == [{'direction': 'IN', 'loads': [1, 2]}, {'direction': 'OUT', 'loads': [2, 1]}]
    assert good[0]['times'] == ['2026-11-01T23:35+09:00', '2026-11-01T23:40+09:00', '2026-11-01T23:50+09:00']
    assert good[1]['times'] == ['2026-11-02T08:20+09:00', '2026-11-02T08:32+09:00', '2026-11-02T08:38+09:00']

    mutations = {}
    def detect(name, mutate, required):
        plan = deepcopy(good)
        mutate(plan)
        found = validate_plan(tables, settings, canonical(plan))['errors']
        assert required in found, (name, found)
        mutations[name] = found
    detect('E02_missing', lambda p: p[0]['assignments'].pop(), 'coverage')
    detect('E02_duplicate', lambda p: p[0]['assignments'].append(deepcopy(p[0]['assignments'][1])), 'coverage')
    detect('OFF_person', lambda p: p[0]['assignments'].append({'employee_id': 'E03', 'board': 'A', 'alight': 'S1'}), 'unexpected-person-date')
    detect('unknown_person', lambda p: p[0]['assignments'][0].update(employee_id='E99'), 'coverage')
    detect('wrong_work_date', lambda p: p[0].update(work_date='2026-11-01'), 'coverage')
    detect('unknown_stop', lambda p: p[0]['path'].__setitem__(0, 'C'), 'candidate-stop')
    detect('wrong_direction', lambda p: p[0].update(direction='OUT'), 'directional-edge')
    detect('wrong_leg_time', lambda p: p[0]['times'].__setitem__(1, '2026-11-01T23:41+09:00'), 'travel-time')
    detect('late_arrival', lambda p: p[0]['times'].__setitem__(2, '2026-11-02T00:00+09:00'), 'arrival')
    detect('early_departure', lambda p: p[1]['times'].__setitem__(0, '2026-11-02T08:19+09:00'), 'departure')
    detect('midnight_wrong_calendar_day', lambda p: p[0].update(times=[t.replace('2026-11-01', '2026-11-02') for t in p[0]['times']]), 'arrival')
    off_bundle = deepcopy(bundle)
    off_bundle['work_schedule'] = off_bundle['work_schedule'].replace('E02,2026-11-02,N,WORK', 'E02,2026-11-02,N,OFF')
    off_tables = validate_input(freeze_bundle(off_bundle)[0])
    assert 'coverage' in validate_plan(off_tables, settings, good_text)['errors']
    mutations['E02_changed_to_OFF'] = validate_plan(off_tables, settings, good_text)['errors']
    limited = validate_plan(tables, settings | {'capacity': 1}, good_text)
    assert 'capacity' in limited['errors']
    mutations['capacity_one'] = limited['errors']
    more_buffer = validate_plan(tables, settings | {'arrival_buffer': 25}, good_text)
    assert 'arrival' in more_buffer['errors']
    mutations['arrival_buffer_25_old_plan'] = more_buffer['errors']
    assert validate_plan(tables, settings | {'arrival_buffer': 25},
                         canonical(create_plan(tables, settings | {'arrival_buffer': 25})))['errors'] == []
    no_history_bundle = deepcopy(bundle)
    no_history_bundle['ridership'] = 'employee_id,rate\n'
    no_history = validate_input(freeze_bundle(no_history_bundle)[0])
    assert len(create_plan(no_history, settings)[0]['assignments']) == 2

    boundary = {}
    for n in (45, 46):
        rows = validate_input(freeze_bundle(many_workers(bundle, n))[0])
        all_together = create_plan(rows, settings | {'capacity': n})
        errors = validate_plan(rows, settings, canonical(all_together))['errors']
        assert errors == ([] if n == 45 else ['capacity'])
        batched = create_plan(rows, settings)
        assert validate_plan(rows, settings, canonical(batched))['errors'] == []
        boundary[str(n)] = {'one_trip_each_direction_errors': errors, 'batched_total_trips': len(batched)}

    input_rejections = {}
    invalid_inputs = {
        'missing_file': lambda b: b.pop('ridership'),
        'wrong_header': lambda b: b.__setitem__('sites', 'bad,name\nS1,공장\n'),
        'unknown_employee': lambda b: b.__setitem__('work_schedule', b['work_schedule'].replace('E02,', 'E99,')),
        'unknown_employee_stop_Z': lambda b: b.__setitem__('employees', b['employees'].replace('E02,S1,B', 'E02,S1,Z')),
        'duplicate_schedule': lambda b: b.__setitem__('work_schedule', b['work_schedule'] + 'E02,2026-11-02,N,WORK\n'),
        'invalid_date': lambda b: b.__setitem__('work_schedule', b['work_schedule'].replace('2026-11-02', '2026-02-30')),
        'negative_travel': lambda b: b.__setitem__('travel_times', b['travel_times'].replace('IN,A,B,5', 'IN,A,B,-5')),
    }
    for name, mutate in invalid_inputs.items():
        altered = deepcopy(bundle)
        mutate(altered)
        try:
            validate_input(freeze_bundle(altered)[0])
        except ValueError as error:
            input_rejections[name] = str(error)
        else:
            raise AssertionError(name)

    with tempfile.TemporaryDirectory(prefix='four-questions-') as folder:
        path = Path(folder) / 'lab.sqlite'
        db = connect(path)
        assert db.execute('SELECT data_version FROM state').fetchone()[0] is None
        apply_dataset(db, text, digest)
        first = start_job(db, 'normal-request')
        plan_text, receipt = prepare(db, first)
        publish(db, first, plan_text, receipt)
        exported = export_plan(db, first)
        assert exported['current'] and exported['plan_json'] == plan_text == good_text
        assert start_job(db, 'normal-request') == first
        expect_error(lambda: publish(db, first, plan_text, receipt))
        assert db.execute('SELECT count(*) FROM finals').fetchone()[0] == 1

        # Ordinary validation failure leaves prior official result unchanged.
        bad_job = start_job(db, 'invalid-candidate')
        bad_plan = deepcopy(good)
        bad_plan[0]['assignments'].pop()
        bad_text = canonical(bad_plan)
        bad_report = validate_plan(tables, settings, bad_text)
        fail_job(db, bad_job, bad_report)
        expect_error(lambda: publish(db, bad_job, bad_text, bad_report))
        assert export_plan(db, bad_job) is None
        assert db.execute('SELECT final_id FROM state').fetchone()[0] == 1

        # A checked string cannot silently turn into another candidate.
        changed = good_text + ' '
        expect_error(lambda: publish(db, start_job(db, 'changed-candidate'), changed, receipt))

        # Bad input, hash mismatch and injected exception preserve all DB state.
        before = list(db.iterdump())
        wrong = deepcopy(bundle)
        wrong['employees'] = wrong['employees'].replace('E02,S1,B', 'E02,S9,B')
        wrong_text, wrong_digest = freeze_bundle(wrong)
        expect_error(lambda: apply_dataset(db, wrong_text, wrong_digest))
        wrong_stop = deepcopy(bundle)
        wrong_stop['employees'] = wrong_stop['employees'].replace('E02,S1,B', 'E02,S1,Z')
        wrong_stop_text, wrong_stop_digest = freeze_bundle(wrong_stop)
        expect_error(lambda: apply_dataset(db, wrong_stop_text, wrong_stop_digest))
        assert list(db.iterdump()) == before
        expect_error(lambda: apply_dataset(db, text, 'wrong-hash'))
        expect_error(lambda: apply_dataset(db, text, digest, inject_failure=True), RuntimeError)
        assert list(db.iterdump()) == before

        # A report for different input/conditions cannot authorize this candidate.
        foreign_report_job = start_job(db, 'foreign-validator-report')
        foreign_settings = validate_plan(tables, settings | {'capacity': 999}, good_text)
        expect_error(lambda: publish(db, foreign_report_job, good_text, foreign_settings))
        foreign_input = validate_plan(no_history, settings, good_text)
        expect_error(lambda: publish(db, foreign_report_job, good_text, foreign_input))

        # Same versions do not make every past success the currently selected one.
        second = start_job(db, 'second-result-same-input')
        second_plan, second_report = prepare(db, second)
        publish(db, second, second_plan, second_report)
        assert export_plan(db, second)['current']
        assert not export_plan(db, first)['current']

        # Freeze an old job; all seven new CSV contents move together.
        old_data_job = start_job(db, 'old-data')
        old_plan, old_report = prepare(db, old_data_job)
        revised = deepcopy(bundle)
        replacements = {'sites': ('공장', '새공장'), 'shifts': ('08:10', '08:15'),
                        'employees': ('E01,S1,A,가', 'E01,S1,A,새이름'),
                        'work_schedule': ('E03,2026-11-02,N,OFF', 'E03,2026-11-02,N,WORK'),
                        'stops': ('정류장A', '새정류장A'), 'travel_times': ('IN,A,B,5', 'IN,A,B,6'),
                        'ridership': ('E01,1', 'E01,0.8')}
        for name, (old, new) in replacements.items():
            revised[name] = revised[name].replace(old, new)
            assert revised[name] != bundle[name]
        new_text, new_digest = freeze_bundle(revised)
        new_version = apply_dataset(db, new_text, new_digest)
        stored = db.execute('SELECT bundle_json FROM datasets WHERE version=?', (new_version,)).fetchone()[0]
        assert json.loads(stored) == revised
        expect_error(lambda: publish(db, old_data_job, old_plan, old_report))
        assert not export_plan(db, first)['current']
        expect_error(lambda: start_job(db, 'normal-request'))

        # Restore toy input, then change settings before final commit.
        apply_dataset(db, text, digest)
        old_setting_job = start_job(db, 'old-settings')
        old_plan, old_report = prepare(db, old_setting_job)
        change_settings(db, capacity=44)
        expect_error(lambda: publish(db, old_setting_job, old_plan, old_report))
        current_job = start_job(db, 'current-job')
        current_plan, current_report = prepare(db, current_job)
        db.execute("UPDATE jobs SET status='CANCEL_REQUESTED' WHERE id=?", (current_job,))
        expect_error(lambda: publish(db, current_job, current_plan, current_report))

        # Persist RUNNING, reconnect: state record is not a living execution.
        interrupted = start_job(db, 'interrupted-at-startup')
        db.close()
        db = connect(path)
        assert db.execute('SELECT status FROM jobs WHERE id=?', (interrupted,)).fetchone()[0] == 'RUNNING'
        recovered_count = recover_single_process(db)
        assert recovered_count >= 1
        assert db.execute('SELECT status FROM jobs WHERE id=?', (interrupted,)).fetchone()[0] == 'INTERRUPTED'
        assert export_plan(db, first)['plan_json'] == good_text
        db.close()

    print(json.dumps({
        'example': 'four_questions', 'status': 'passed',
        'expected_assignments': ['E01/2026-11-02/IN', 'E01/2026-11-02/OUT', 'E02/2026-11-02/IN', 'E02/2026-11-02/OUT'],
        'normal_segment_loads': report['segment_loads'], 'plan_mutations_detected': mutations,
        'input_rejections': input_rejections, 'capacity_boundary': boundary,
        'database_checks': ['empty-initialization', 'seven-files-snapshot-apply', 'invalid-input-keeps-state',
                            'changed-hash-rejected', 'injected-exception-rolls-back', 'checked-stored-exported-same-json',
                            'invalid-candidate-keeps-final', 'changed-candidate-rejected', 'stale-data-rejected',
                            'stale-settings-rejected', 'non-running-job-rejected', 'old-result-marked-historical',
                            'same-key-same-job', 'one-final-per-job', 'post-commit-lookup-by-job',
                            'different-validation-input-or-settings-rejected', 'superseded-final-marked-historical',
                            'reconnect-keeps-final-and-running', 'exclusive-single-process-startup-cleanup'],
        'history_check': 'empty history rows keep both WORK people; ridership file/header still required',
        'limits': ['teaching CSV schema; seven files stored in one immutable JSON snapshot',
                   'fixed path one-day one-site one-shift toy Creator; no optimization proof',
                   'Validator assumes documented JSON shape; not a hostile-JSON schema validator',
                   'no real HTTP/auth/Worker/kill/deadline/cancel-delivery/multi-server/performance tests',
                   'startup cleanup simulates abandoned RUNNING; exclusive ownership is a premise',
                   'no exam submission or actual CSV verification'],
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
