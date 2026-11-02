"""Exhaustive oracle for one tiny covering model, not a full bus optimizer."""
import itertools
import json

TARGET = {"E1", "E2", "E3"}
ROUTES = {"A": ({"E1", "E2"}, 5), "B": ({"E3"}, 4), "C": (TARGET, 12)}


def feasible(names):
    occurrences = [emp for name in names for emp in ROUTES[name][0]]
    return len(occurrences) == len(set(occurrences)) and set(occurrences) == TARGET


def cost(names):
    return sum(ROUTES[name][1] for name in names)


def main():
    baseline = ("C",)
    assert feasible(baseline)
    choices = [names for size in range(1, 4)
               for names in itertools.combinations(ROUTES, size) if feasible(names)]
    best = min(choices, key=cost)
    assert best == ("A", "B") and cost(best) == 9
    assert cost(baseline) == 12
    assert not feasible(("A",)) and not feasible(("A", "C"))
    print(json.dumps({"baseline_cost": 12, "tiny_model_optimum": 9,
                      "improvement_fraction": (12 - 9) / 12,
                      "global_bus_optimality_proven": False}))


if __name__ == "__main__":
    main()
