from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

import psycopg
from psycopg.rows import dict_row

from db.sql import load_query


def database_url_from_config(config) -> str:
    return os.environ.get("DATABASE_URL") or config.get("DATABASE_URL", "")


class Database:
    def __init__(self, database_url: str, logger=None):
        self.database_url = database_url
        self.logger = logger

    @property
    def configured(self) -> bool:
        return bool(self.database_url)

    @contextmanager
    def connection(self) -> Iterator[psycopg.Connection]:
        if not self.database_url:
            raise RuntimeError("DATABASE_URL is not configured.")

        conn = psycopg.connect(self.database_url, row_factory=dict_row)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def health_check(self) -> bool:
        if not self.configured:
            return False
        try:
            with self.connection() as conn:
                conn.execute(load_query("health_check.sql"))
            return True
        except Exception as exc:
            if self.logger:
                self.logger.warning(f"Database health check failed: {exc}")
            return False
