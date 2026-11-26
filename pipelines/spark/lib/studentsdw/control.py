from __future__ import annotations

import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator

import psycopg2

from .clickhouse import ClickHouseClient
from .config import Postgres


@contextmanager
def _connection(cfg: Postgres | None = None) -> Iterator[psycopg2.extensions.connection]:
    conn = psycopg2.connect(**(cfg or Postgres()).dsn())
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def start_batch(pipeline: str) -> tuple[int, int]:
    snapshot_ms = int(time.time() * 1000)
    with _connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT nextval('control.batch_id_seq')")
        batch_id = int(cur.fetchone()[0])
        cur.execute("INSERT INTO control.etl_batch (batch_id, pipeline, snapshot_ms) VALUES (%s, %s, %s)",
                    (batch_id, pipeline, snapshot_ms))
    return batch_id, snapshot_ms


def finish_batch(batch_id: int, status: str, message: str | None = None) -> None:
    with _connection() as conn, conn.cursor() as cur:
        cur.execute("UPDATE control.etl_batch SET status = %s, finished_at = now(), message = %s WHERE batch_id = %s",
                    (status, message, batch_id))


def next_batch_id() -> int:
    with _connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT nextval('control.batch_id_seq')")
        return int(cur.fetchone()[0])


def allocate_keys(sequence: str, count: int) -> int:
    if count <= 0:
        return 0
    with _connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (sequence,))
        cur.execute(f"SELECT nextval('control.{sequence}')")
        first = int(cur.fetchone()[0])
        cur.execute(f"SELECT setval('control.{sequence}', %s)", (first + count - 1,))
    return first


def log_extract(batch_id: int, table: str, rows: int, duration_ms: int) -> None:
    with _connection() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO control.extract_log (batch_id, table_name, row_count, duration_ms) VALUES (%s, %s, %s, %s) "
            "ON CONFLICT (batch_id, table_name) DO UPDATE SET row_count = EXCLUDED.row_count, "
            "duration_ms = EXCLUDED.duration_ms, loaded_at = now()",
            (batch_id, table, rows, duration_ms))


def pg_query(sql: str, params: tuple = ()) -> list[tuple]:
    with _connection() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall() if cur.description else []


class StepLog:

    def __init__(self, ch: ClickHouseClient, batch_id: int, pipeline: str, step: str) -> None:
        self.ch, self.batch_id, self.pipeline, self.step = ch, batch_id, pipeline, step
        self.rows_read = 0
        self.rows_written = 0
        self.message = ""

    def __enter__(self) -> "StepLog":
        self.started = datetime.now(timezone.utc)
        return self

    def __exit__(self, exc_type, exc, _tb) -> bool:
        status = "failed" if exc else "success"
        message = f"{exc_type.__name__}: {exc}"[:2000] if exc else self.message
        try:
            self.ch.insert_rows("etl_step_log", [{
                "batch_id": self.batch_id, "pipeline": self.pipeline, "step": self.step, "status": status,
                "rows_read": self.rows_read, "rows_written": self.rows_written,
                "started_at": self.started.isoformat(), "finished_at": datetime.now(timezone.utc).isoformat(),
                "message": message,
            }])
        except Exception as log_error:
            print(f"[step-log] could not record step {self.step}: {log_error}")
        return False
