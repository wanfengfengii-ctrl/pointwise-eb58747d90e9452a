from collections import deque


class Closure:
    """Maintain C(x,z) <- E(x,z) or C(x,y) and E(y,z).

    support counts direct-edge support plus distinct final-edge witnesses.
    Only transitions between absent and present propagate downstream.
    """
    def __init__(self, store):
        self.store = store

    def _adjust(self, src, dst, delta, pending):
        old = self.store.support(src, dst)
        new = old + delta
        if new < 0:
            raise RuntimeError("negative closure support")
        self.store.set_support(src, dst, new)
        if (old == 0) != (new == 0):
            pending.append((src, dst))

    def _drain(self, pending, delta):
        while pending:
            src, middle = pending.popleft()
            for dst in self.store.outgoing(middle):
                self._adjust(src, dst, delta, pending)

    def insert(self, src, dst):
        if self.store.has_edge(src, dst):
            return
        predecessors = self.store.predecessors(src)
        self.store.add_edge(src, dst)
        pending = deque()
        self._adjust(src, dst, 1, pending)
        for root in predecessors:
            self._adjust(root, dst, 1, pending)
        self._drain(pending, 1)

    def delete(self, src, dst):
        if not self.store.has_edge(src, dst):
            return
        predecessors = self.store.predecessors(src)
        self.store.remove_edge(src, dst)
        pending = deque()
        self._adjust(src, dst, -1, pending)
        for root in predecessors:
            self._adjust(root, dst, -1, pending)
        self._drain(pending, -1)

    def apply(self, add, remove):
        for src, dst in sorted(remove):
            self.delete(src, dst)
        for src, dst in sorted(add):
            self.insert(src, dst)
