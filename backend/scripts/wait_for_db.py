"""Block until PostgreSQL accepts connections (used by the Docker entrypoint)."""
from __future__ import annotations

import os
import sys
import time
from urllib.parse import unquote, urlparse

import psycopg2


def main() -> int:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        print("DATABASE_URL is not set.", file=sys.stderr)
        return 1

    parsed = urlparse(url.replace("postgresql+psycopg2://", "postgresql://", 1))
    if parsed.scheme not in ("postgres", "postgresql") or not parsed.hostname:
        print("DATABASE_URL must be a PostgreSQL URL.", file=sys.stderr)
        return 1
    connection = {
        "host": parsed.hostname,
        "port": parsed.port or 5432,
        "dbname": parsed.path.lstrip("/"),
    }
    if parsed.username:
        connection["user"] = unquote(parsed.username)
    if parsed.password:
        connection["password"] = unquote(parsed.password)

    attempts = 60
    for i in range(1, attempts + 1):
        try:
            psycopg2.connect(**connection).close()
            print(f"PostgreSQL is ready (after {i} attempt(s)).")
            return 0
        except Exception as exc:  # noqa: BLE001
            print(f"Waiting for PostgreSQL ({i}/{attempts}): {exc}")
            time.sleep(2)

    print("PostgreSQL did not become ready in time.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
