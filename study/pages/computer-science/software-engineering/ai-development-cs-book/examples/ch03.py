"""A small executable requirements-to-test trace, not an understanding grader."""
import json


def within_capacity(count, capacity):
    return 0 <= count <= capacity


def targets(rows):
    return {row["id"] for row in rows if row["status"] == "WORK"}


def same_version(candidate, current):
    return candidate == current


def test_capacity():
    assert within_capacity(45, 45)
    assert not within_capacity(46, 45)


def test_off():
    assert targets([{"id": "E1", "status": "WORK"}, {"id": "E2", "status": "OFF"}]) == {"E1"}


def test_version():
    assert same_version(2, 2)
    assert not same_version(1, 2)


def main():
    trace = {"R-CAP": (within_capacity, test_capacity),
             "R-OFF": (targets, test_off), "R-VER": (same_version, test_version)}
    for requirement, (implementation, test) in trace.items():
        assert callable(implementation), requirement
        test()
    print(json.dumps({"mapped_requirements": sorted(trace), "tests_passed": len(trace),
                      "atomic_publication_proven": False}))


if __name__ == "__main__":
    main()
