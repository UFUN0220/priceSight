"""Keep API tests deterministic while production development defaults to SQLite."""

import os


os.environ.setdefault("SESSION_STORE_BACKEND", "memory")
