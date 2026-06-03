from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from db.sql import load_query


def database_url_from_config(config) -> str:
    return os.environ.get("DATABASE_URL") or config.get("DATABASE_URL", "")


class Database:
    def __init__(self, database_url: str, logger=None, *, pool_min_size: int | None = None, pool_max_size: int | None = None):
        self.database_url = database_url
        self.logger = logger
        self.pool_min_size = self._positive_int(
            os.environ.get("DATABASE_POOL_MIN_SIZE"),
            default=pool_min_size if pool_min_size is not None else 1,
        )
        self.pool_max_size = self._positive_int(
            os.environ.get("DATABASE_POOL_MAX_SIZE"),
            default=pool_max_size if pool_max_size is not None else 12,
        )
        if self.pool_max_size < self.pool_min_size:
            self.pool_max_size = self.pool_min_size
        self._pool: ConnectionPool | None = None

    @staticmethod
    def _positive_int(value, *, default: int) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = int(default)
        return max(1, parsed)

    @property
    def configured(self) -> bool:
        return bool(self.database_url)

    def _connection_pool(self) -> ConnectionPool:
        if not self.database_url:
            raise RuntimeError("DATABASE_URL is not configured.")
        if self._pool is None:
            self._pool = ConnectionPool(
                self.database_url,
                min_size=self.pool_min_size,
                max_size=self.pool_max_size,
                kwargs={"row_factory": dict_row},
                open=False,
            )
            self._pool.open(wait=True)
            if self.logger:
                self.logger.info(
                    f"PostgreSQL connection pool opened: min={self.pool_min_size}, max={self.pool_max_size}"
                )
        return self._pool

    @contextmanager
    def connection(self) -> Iterator[psycopg.Connection]:
        if not self.database_url:
            raise RuntimeError("DATABASE_URL is not configured.")

        pool = self._connection_pool()
        conn = pool.getconn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            pool.putconn(conn)

    def pool_stats(self) -> dict:
        if not self._pool:
            return {
                "enabled": True,
                "open": False,
                "minSize": self.pool_min_size,
                "maxSize": self.pool_max_size,
            }
        stats = self._pool.get_stats()
        return {
            "enabled": True,
            "open": True,
            "minSize": self.pool_min_size,
            "maxSize": self.pool_max_size,
            **{self._camel_case(key): value for key, value in stats.items()},
        }

    @staticmethod
    def _camel_case(value: str) -> str:
        parts = str(value).split("_")
        return parts[0] + "".join(part[:1].upper() + part[1:] for part in parts[1:])

    def close(self) -> None:
        if self._pool:
            self._pool.close()
            self._pool = None

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
