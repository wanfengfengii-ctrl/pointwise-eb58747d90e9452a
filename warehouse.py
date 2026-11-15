from closure import Closure
from store import IndexedStore


def _edges(values):
    result = set()
    for item in values:
        if not isinstance(item, (tuple, list)) or len(item) != 2:
            raise ValueError("edge must have two endpoints")
        if any(not isinstance(x, str) or not x for x in item):
            raise ValueError("endpoints must be nonempty strings")
        result.add(tuple(item))
    return result


class Warehouse:
    def __init__(self, path=":memory:"):
        self.store = IndexedStore(path)
        self.closure = Closure(self.store)
        self.metrics = dict(self.store.counts)

    def apply(self, add=(), remove=()):
        add, remove = _edges(add), _edges(remove)
        if add & remove:
            raise ValueError("add and remove overlap")
        self.store.reset_metrics()
        self.store.db.execute("BEGIN IMMEDIATE")
        try:
            self.closure.apply(add, remove)
            self.store.db.execute("COMMIT")
        except BaseException:
            self.store.db.execute("ROLLBACK")
            raise
        finally:
            self.metrics = dict(self.store.counts)

    def reachable(self):
        return self.store.reachable()

    def edges(self):
        return self.store.edges()

    def close(self):
        self.store.close()
