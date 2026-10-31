"""Responsibility boundaries in a single-thread in-memory model."""
import json
from dataclasses import dataclass, FrozenInstanceError


@dataclass(frozen=True)
class Input:
    version: int
    workers: tuple[str, ...]


@dataclass(frozen=True)
class Candidate:
    version: int
    assignments: tuple[str, ...]


def create(snapshot):
    return Candidate(snapshot.version, snapshot.workers)


def validate(snapshot, plan):
    return (plan.version == snapshot.version
            and set(plan.assignments) == set(snapshot.workers)
            and len(plan.assignments) == len(set(plan.assignments)))


class Repository:
    def __init__(self):
        self.version, self.final = 1, None

    def publish(self, plan):
        if plan.version != self.version:
            return False
        self.final = plan
        return True


def main():
    snapshot = Input(1, ("E1", "E2"))
    plan = create(snapshot)
    assert validate(snapshot, plan)
    repository = Repository()
    repository.version = 2
    assert not repository.publish(plan)
    assert repository.final is None
    try:
        snapshot.version = 3
        raise AssertionError("frozen field changed")
    except FrozenInstanceError:
        pass
    assert not validate(snapshot, Candidate(1, ("E1", "E1")))
    print(json.dumps({"candidate_valid": True, "stale_publication_rejected": True,
                      "repository_scope": "single-thread-memory"}))


if __name__ == "__main__":
    main()
