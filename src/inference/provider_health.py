"""Persistent per-model circuit breaker state for the managed FreeLLM gateway.

Set NEXUS_PROVIDER_HEALTH_DB to a path on a persistent disk in production.
"""
from __future__ import annotations

import os
import sqlite3
import threading
import time
from pathlib import Path

_LOCK = threading.Lock()
_FAILURE_THRESHOLD = 3
_COOLDOWN_SECONDS = 60


def _connect():
    path = os.environ.get("NEXUS_PROVIDER_HEALTH_DB", "vonk_provider_health.sqlite3")
    if path != ":memory:":
        Path(path).expanduser().parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=5)
    connection.execute(
        """CREATE TABLE IF NOT EXISTS provider_health (
            model_id TEXT PRIMARY KEY,
            failures INTEGER NOT NULL DEFAULT 0,
            open_until REAL NOT NULL DEFAULT 0,
            last_error_at REAL,
            last_success_at REAL
        )"""
    )
    return connection


def is_available(model_id: str) -> bool:
    try:
        with _LOCK, _connect() as db:
            row = db.execute(
                "SELECT open_until FROM provider_health WHERE model_id = ?",
                (model_id,),
            ).fetchone()
        return not row or float(row[0]) <= time.time()
    except (OSError, sqlite3.Error, ValueError):
        # Health persistence must never take the inference service offline.
        return True


def record_success(model_id: str) -> None:
    try:
        with _LOCK, _connect() as db:
            db.execute(
                """INSERT INTO provider_health
                   (model_id, failures, open_until, last_success_at)
                   VALUES (?, 0, 0, ?)
                   ON CONFLICT(model_id) DO UPDATE SET
                     failures=0, open_until=0, last_success_at=excluded.last_success_at""",
                (model_id, time.time()),
            )
    except (OSError, sqlite3.Error):
        return


def record_failure(model_id: str, error_kind: str) -> None:
    # Authentication and invalid-request failures are not provider-health failures.
    if error_kind not in {"timeout", "network", "rate_limit", "upstream"}:
        return
    now = time.time()
    try:
        with _LOCK, _connect() as db:
            row = db.execute(
                "SELECT failures FROM provider_health WHERE model_id = ?",
                (model_id,),
            ).fetchone()
            failures = (int(row[0]) if row else 0) + 1
            open_until = now + _COOLDOWN_SECONDS if failures >= _FAILURE_THRESHOLD else 0
            db.execute(
                """INSERT INTO provider_health
                   (model_id, failures, open_until, last_error_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(model_id) DO UPDATE SET
                     failures=excluded.failures, open_until=excluded.open_until,
                     last_error_at=excluded.last_error_at""",
                (model_id, failures, open_until, now),
            )
    except (OSError, sqlite3.Error):
        return


def snapshot() -> list[dict]:
    try:
        with _LOCK, _connect() as db:
            rows = db.execute(
                """SELECT model_id, failures, open_until, last_error_at, last_success_at
                   FROM provider_health ORDER BY model_id"""
            ).fetchall()
        now = time.time()
        return [
            {
                "model": row[0],
                "consecutive_failures": row[1],
                "circuit": "open" if row[2] > now else "closed",
                "retry_after_seconds": max(0, int(row[2] - now)),
                "last_error_at": row[3],
                "last_success_at": row[4],
            }
            for row in rows
        ]
    except (OSError, sqlite3.Error):
        return []
