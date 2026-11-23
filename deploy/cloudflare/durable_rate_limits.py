"""Flask-Limiter fixed windows backed by a Durable Object's SQLite storage."""
from contextvars import ContextVar
from time import time

from limits.storage import Storage

request_sql = ContextVar("request_sql")


class DurableRateLimits(Storage):
    STORAGE_SCHEME = ["durable-sqlite"]
    base_exceptions = Exception

    def incr(self, key, expiry, amount=1):
        now = int(time())
        sql = request_sql.get()
        return sql.exec(
            """INSERT INTO rate_limits (key, hits, expires) VALUES (?, ?, ?)
               ON CONFLICT (key) DO UPDATE SET
                 hits = CASE WHEN expires <= ? THEN excluded.hits ELSE hits + excluded.hits END,
                 expires = CASE WHEN expires <= ? THEN excluded.expires ELSE expires END
               RETURNING hits""",
            key, amount, now + expiry, now, now,
        ).one().hits

    def get(self, key):
        return request_sql.get().exec(
            "SELECT coalesce(max(hits), 0) AS value FROM rate_limits WHERE key = ? AND expires > ?",
            key, int(time()),
        ).one().value

    def get_expiry(self, key):
        return request_sql.get().exec(
            "SELECT coalesce(max(expires), ?) AS value FROM rate_limits WHERE key = ? AND expires > ?",
            int(time()), key, int(time()),
        ).one().value

    def check(self):
        return request_sql.get().exec("SELECT 1 AS ready").one().ready == 1

    def reset(self):
        return request_sql.get().exec("DELETE FROM rate_limits").rowsWritten

    def clear(self, key):
        request_sql.get().exec("DELETE FROM rate_limits WHERE key = ?", key)
