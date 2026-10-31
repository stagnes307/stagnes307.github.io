"""Dependency schedule plus a global error missed by local uniqueness checks."""
import json
from graphlib import TopologicalSorter


def main():
    graph = TopologicalSorter({"employees": set(), "travel": set(),
                               "create": {"employees", "travel"},
                               "validate": {"create"}, "publish": {"validate"}})
    graph.prepare()
    first = set(graph.get_ready())
    assert first == {"employees", "travel"}
    graph.done(*first)
    assert set(graph.get_ready()) == {"create"}
    graph.done("create")
    assert set(graph.get_ready()) == {"validate"}
    graph.done("validate")
    assert set(graph.get_ready()) == {"publish"}
    graph.done("publish")
    chunks = [("E1",), ("E1",)]
    local_ok = all(len(chunk) == len(set(chunk)) for chunk in chunks)
    merged = sum(chunks, ())
    global_ok = len(merged) == len(set(merged)) and set(merged) == {"E1", "E2"}
    assert local_ok and not global_ok
    print(json.dumps({"independent_first": sorted(first),
                      "order": ["create", "validate", "publish"],
                      "local_pass_global_fail": True}))


if __name__ == "__main__":
    main()
