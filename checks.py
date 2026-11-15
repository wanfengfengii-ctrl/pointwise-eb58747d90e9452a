import json
import random
import sys

from samples import INCIDENT, DISCONNECT, EXPECTED_AFTER
from warehouse import Warehouse

MARKER = "LINEAGE_CYCLE_RETRACTION"


def reference(edges):
    # Independent full traversal for verification only.
    adjacency = {}
    for src, dst in edges:
        adjacency.setdefault(src, set()).add(dst)
    result = set()
    for root in adjacency:
        seen = set()
        todo = list(adjacency[root])
        while todo:
            node = todo.pop()
            if node in seen:
                continue
            seen.add(node)
            todo.extend(adjacency.get(node, ()))
        result.update((root, node) for node in seen)
    return sorted(result)


def compare(warehouse, edges):
    assert warehouse.edges() == sorted(edges), "source edge mismatch"
    expected = reference(edges)
    actual = warehouse.reachable()
    assert actual == expected, (expected, actual)


def regression():
    w = Warehouse()
    edges = set()
    operations = [
        ([("a", "b"), ("a", "c"), ("b", "d"), ("c", "d")], []),
        ([], [("b", "d")]),
        ([("c", "d"), ("a", "c")], [("absent", "d")]),
        ([("a", "d")], [("c", "d")]),
        ([("d", "e")], []),
        ([], [("a", "d")]),
        ([], []),
    ]
    for add, remove in operations:
        w.apply(add, remove)
        edges.difference_update(remove)
        edges.update(add)
        compare(w, edges)
    before = w.edges(), w.reachable()
    for add, remove in [
        ([("a", "")], []),
        ([("x", "y"), ("bad",)], []),
        ([("x", "y")], [("x", "y")]),
    ]:
        try:
            w.apply(add, remove)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid batch was accepted")
        assert (w.edges(), w.reachable()) == before
    w.close()

    # Closing and then breaking a cycle is an existing supported case.
    w = Warehouse()
    w.apply([("a", "b"), ("b", "a"), ("b", "c")])
    compare(w, {("a", "b"), ("b", "a"), ("b", "c")})
    w.apply(remove=[("a", "b")])
    assert w.reachable() == [("b", "a"), ("b", "c")]
    w.close()
    locality(cyclic=False)
    print("REGRESSION_OK: diamond, replacement, no-op, validation, cycle edge")


def reproduce():
    w = Warehouse()
    try:
        w.apply(INCIDENT)
        compare(w, set(INCIDENT))
        w.apply(remove=DISCONNECT)
        actual = w.reachable()
        if actual != EXPECTED_AFTER:
            print(MARKER, flush=True)
            print(json.dumps({"expected": EXPECTED_AFTER, "actual": actual},
                             ensure_ascii=False, sort_keys=True), flush=True)
            raise AssertionError(MARKER)
        print("CYCLE_RETRACTION_OK")
    finally:
        w.close()


def randomized():
    rng = random.Random(61073)
    vertices = ["n" + str(i) for i in range(8)]
    universe = [(a, b) for a in vertices for b in vertices]
    w = Warehouse()
    edges = set()
    try:
        for step in range(180):
            touched = rng.sample(universe, rng.randrange(1, 6))
            add, remove = [], []
            for edge in touched:
                (add if rng.randrange(2) else remove).append(edge)
            w.apply(add, remove)
            edges.difference_update(remove)
            edges.update(add)
            compare(w, edges)
        print("RANDOM_REFERENCE_OK")
    finally:
        w.close()


def locality(cyclic=True):
    for size in (200, 2000):
        # Many untouched branches of the affected source, plus a disconnected
        # stable chain: recomputing sources or scanning the warehouse is visible.
        edges = {("root", "leaf-" + str(i)) for i in range(size)}
        edges.update(("stable-" + str(i), "stable-" + str(i + 1))
                     for i in range(60))
        edges.update({("root", "u"), ("u", "v")})
        if cyclic:
            edges.add(("v", "u"))
        w = Warehouse()
        try:
            w.apply(edges)
            w.apply(remove=[("root", "u")])
            metrics = dict(w.metrics)
            edges.remove(("root", "u"))
            compare(w, edges)
            assert metrics["full_scans"] == 0, metrics
            work = (metrics["point_probes"] + metrics["range_calls"]
                    + metrics["index_rows"])
            assert work <= 100, (size, work, metrics)
            print("LOCALITY", json.dumps(
                {"stable_branches": size, "metrics": metrics}, sort_keys=True))
        finally:
            w.close()


def demo():
    w = Warehouse()
    try:
        w.apply(INCIDENT)
        print(json.dumps({"edges_before": w.edges(),
                          "reachable_before": w.reachable()}, sort_keys=True))
        w.apply(remove=DISCONNECT)
        print(json.dumps({"removed": DISCONNECT,
                          "edges_after": w.edges(),
                          "reachable_after": w.reachable(),
                          "expected_after": EXPECTED_AFTER,
                          "metrics": w.metrics}, sort_keys=True))
    finally:
        w.close()


def verify():
    regression()
    reproduce()
    randomized()
    locality()
    print("VERIFY_OK")


if __name__ == "__main__":
    actions = {"regression": regression, "reproduce": reproduce,
               "verify": verify, "demo": demo}
    if len(sys.argv) != 2 or sys.argv[1] not in actions:
        raise SystemExit("usage: python3 checks.py regression|reproduce|verify|demo")
    actions[sys.argv[1]]()
