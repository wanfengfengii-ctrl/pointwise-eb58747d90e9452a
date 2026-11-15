from collections import deque


class Closure:
    """Maintain reach(x, z) <- a nonempty directed path x ->+ z exists.

    The relation is maintained as a set: a stored row means reachable.
    Insert and delete both work on the same local window: the pairs whose
    paths may gain or lose edge (src, dst) are exactly
    (pred*(src) + src) x (succ*(dst) + dst), read from the materialized
    closure through the bidirectional indexes. Nothing outside that
    window is touched, so untouched branches of an affected source and
    disconnected parts of the graph are never re-walked.
    """
    def __init__(self, store):
        self.store = store

    def _present(self, src, dst):
        return self.store.support(src, dst) > 0

    def _window(self, src, dst):
        # Every x that reaches src (src included) paired with every y
        # reachable from dst (dst included): the only pairs whose path
        # set can contain or gain a path through edge (src, dst).
        xs = set(self.store.predecessors(src))
        xs.add(src)
        ys = set(self.store.successors(dst))
        ys.add(dst)
        return xs, ys

    def insert(self, src, dst):
        if self.store.has_edge(src, dst):
            return
        xs, ys = self._window(src, dst)
        self.store.add_edge(src, dst)
        # A new path uses the new edge once: x ->* src -> dst ->* y.
        # Pairs already present keep their old paths; add only new ones.
        for x in sorted(xs):
            for y in sorted(ys):
                if not self._present(x, y):
                    self.store.set_support(x, y, 1)

    def delete(self, src, dst):
        if not self.store.has_edge(src, dst):
            return
        xs, ys = self._window(src, dst)
        self.store.remove_edge(src, dst)
        # Over-retract: every pair whose paths may have crossed the
        # removed edge is tentatively withdrawn. Pairs outside the
        # window keep all their paths and are never visited.
        withdrawn = set()
        for x in sorted(xs):
            for y in sorted(ys):
                if self._present(x, y):
                    self.store.set_support(x, y, 0)
                    withdrawn.add((x, y))
        # Rederive: a withdrawn pair (x, y) survives iff edge (x, y)
        # remains or some surviving (x, z) meets a remaining edge z->y.
        # Re-derived pairs propagate the same way inside the window.
        incoming = {y: self.store.incoming(y) for y in sorted(ys)}
        queue = deque()
        for x, y in sorted(withdrawn):
            if self.store.has_edge(x, y) or any(
                    self._present(x, z) for z in incoming[y]):
                queue.append((x, y))
        while queue:
            x, y = queue.popleft()
            if (x, y) not in withdrawn:
                continue
            withdrawn.discard((x, y))
            self.store.set_support(x, y, 1)
            for nxt in self.store.outgoing(y):
                if (x, nxt) in withdrawn:
                    queue.append((x, nxt))

    def apply(self, add, remove):
        for src, dst in sorted(remove):
            self.delete(src, dst)
        for src, dst in sorted(add):
            self.insert(src, dst)
