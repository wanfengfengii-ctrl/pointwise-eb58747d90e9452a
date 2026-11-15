# Table names are graph vertices; each pair is a direct dependency.
INCIDENT = [
    ("raw", "stage"),
    ("stage", "quality"),
    ("quality", "stage"),
    ("quality", "mart"),
]
DISCONNECT = [("raw", "stage")]
EXPECTED_AFTER = [
    ("quality", "mart"), ("quality", "quality"), ("quality", "stage"),
    ("stage", "mart"), ("stage", "quality"), ("stage", "stage"),
]
