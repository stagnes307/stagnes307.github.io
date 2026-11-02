"""Independent miniature plan checker plus deliberate mutations; not real CSV schema."""
from collections import Counter
from datetime import datetime, timedelta
import json


def check(plan, capacity=45):
    expected = Counter((emp, direction) for emp in ('E1', 'E2') for direction in ('IN', 'OUT'))
    actual = Counter((emp, trip['direction']) for trip in plan for emp in trip['people'])
    errors = []
    if actual != expected:
        errors.append('coverage')
    start = datetime.fromisoformat('2026-07-21T00:10')
    end = datetime.fromisoformat('2026-07-21T08:10')
    for trip in plan:
        if len(trip['people']) > capacity:
            errors.append('capacity')
        moment = datetime.fromisoformat(trip['time'])
        if trip['direction'] == 'IN' and not start - timedelta(hours=12) <= moment <= start - timedelta(minutes=20):
            errors.append('arrival')
        if trip['direction'] == 'OUT' and not end + timedelta(minutes=10) <= moment <= end + timedelta(hours=12):
            errors.append('departure')
    return sorted(set(errors))


def main():
    good = [{'direction': 'IN', 'people': ['E1', 'E2'], 'time': '2026-07-20T23:50'},
            {'direction': 'OUT', 'people': ['E1', 'E2'], 'time': '2026-07-21T08:20'}]
    assert not check(good)
    missing = [dict(trip, people=list(trip['people'])) for trip in good]
    missing[0]['people'] = ['E1']
    assert check(missing) == ['coverage']
    late = [dict(trip) for trip in good]
    late[0]['time'] = '2026-07-21T00:00'
    assert check(late) == ['arrival']
    duplicate = [dict(trip, people=list(trip['people'])) for trip in good]
    duplicate[0]['people'].append('E1')
    assert check(duplicate) == ['coverage']
    off = [dict(trip, people=list(trip['people'])) for trip in good]
    off[0]['people'].append('OFF1')
    assert check(off) == ['coverage']
    early = [dict(trip) for trip in good]
    early[1]['time'] = '2026-07-21T08:19'
    assert check(early) == ['departure']
    too_early = [dict(trip) for trip in good]
    too_early[0]['time'] = '2026-07-20T12:09'
    assert check(too_early) == ['arrival']
    too_late = [dict(trip) for trip in good]
    too_late[1]['time'] = '2026-07-21T20:11'
    assert check(too_late) == ['departure']
    # Candidate metadata cannot override the independently supplied capacity.
    forged = [dict(trip, capacity=999) for trip in good]
    assert check(forged, capacity=1) == ['capacity']
    assert check(good, capacity=1) == ['capacity']
    print(json.dumps({'valid_pass': True, 'mutations_detected': ['missing', 'duplicate', 'off', 'arrival', 'departure', 'capacity', 'arrival-too-early', 'departure-too-late', 'forged-capacity'],
                      'midnight_checked': True, 'route_travel_times_checked': False}))


if __name__ == '__main__':
    main()
