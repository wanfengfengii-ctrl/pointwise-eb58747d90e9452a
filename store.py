import sqlite3


class IndexedStore:
    """Persistent source edges and materialized nonempty-path closure."""
    def __init__(self, path):
        self.db = sqlite3.connect(path, isolation_level=None)
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS edge(
                src TEXT NOT NULL, dst TEXT NOT NULL,
                PRIMARY KEY(src, dst)
            ) WITHOUT ROWID;
            CREATE INDEX IF NOT EXISTS edge_reverse ON edge(dst, src);
            CREATE TABLE IF NOT EXISTS reach(
                src TEXT NOT NULL, dst TEXT NOT NULL,
                support INTEGER NOT NULL CHECK(support > 0),
                PRIMARY KEY(src, dst)
            ) WITHOUT ROWID;
            CREATE INDEX IF NOT EXISTS reach_reverse ON reach(dst, src);
        """)
        self.reset_metrics()

    def reset_metrics(self):
        self.counts = {"point_probes": 0, "range_calls": 0,
                       "index_rows": 0, "full_scans": 0}

    def _one(self, sql, args):
        self.counts["point_probes"] += 1
        return self.db.execute(sql, args).fetchone()

    def _range(self, sql, args):
        self.counts["range_calls"] += 1
        rows = self.db.execute(sql, args).fetchall()
        self.counts["index_rows"] += len(rows)
        return rows

    def has_edge(self, src, dst):
        return self._one("SELECT 1 FROM edge WHERE src=? AND dst=?",
                         (src, dst)) is not None

    def outgoing(self, src):
        return [row[0] for row in self._range(
            "SELECT dst FROM edge WHERE src=? ORDER BY dst", (src,))]

    def incoming(self, dst):
        return [row[0] for row in self._range(
            "SELECT src FROM edge WHERE dst=? ORDER BY src", (dst,))]

    def predecessors(self, dst):
        return [row[0] for row in self._range(
            "SELECT src FROM reach WHERE dst=? ORDER BY src", (dst,))]

    def successors(self, src):
        return [row[0] for row in self._range(
            "SELECT dst FROM reach WHERE src=? ORDER BY dst", (src,))]

    def support(self, src, dst):
        row = self._one("SELECT support FROM reach WHERE src=? AND dst=?",
                        (src, dst))
        return 0 if row is None else row[0]

    def set_support(self, src, dst, value):
        if value:
            self.db.execute(
                "INSERT INTO reach VALUES(?,?,?) ON CONFLICT(src,dst) "
                "DO UPDATE SET support=excluded.support", (src, dst, value))
        else:
            self.db.execute("DELETE FROM reach WHERE src=? AND dst=?",
                            (src, dst))

    def add_edge(self, src, dst):
        self.db.execute("INSERT INTO edge VALUES(?,?)", (src, dst))

    def remove_edge(self, src, dst):
        self.db.execute("DELETE FROM edge WHERE src=? AND dst=?", (src, dst))

    def edges(self):
        self.counts["full_scans"] += 1
        return self.db.execute(
            "SELECT src,dst FROM edge ORDER BY src,dst").fetchall()

    def reachable(self):
        self.counts["full_scans"] += 1
        return self.db.execute(
            "SELECT src,dst FROM reach ORDER BY src,dst").fetchall()

    def close(self):
        self.db.close()
