from __future__ import annotations

import json
import os
import tempfile
import time
import uuid
from typing import Any, Iterable, Mapping

import requests

from .config import ClickHouse

_INSERT_SETTINGS = {
    "input_format_skip_unknown_fields": "1",
    "input_format_null_as_default": "1",
    "date_time_input_format": "best_effort",
}


_SESSION: requests.Session | None = None
_RETRIES = 6


def _session() -> requests.Session:
    global _SESSION
    if _SESSION is None:
        _SESSION = requests.Session()
    return _SESSION


def _post(cfg: ClickHouse, sql: str, data: bytes | None = None, params: Mapping[str, Any] | None = None,
          settings: Mapping[str, str] | None = None, stream: bool = False, timeout: int = 600) -> requests.Response:
    query = {"database": cfg.database}
    if settings:
        query.update(settings)
    if params:
        query.update({f"param_{k}": str(v) for k, v in params.items()})
    if data is None:
        body, query_string = sql.encode("utf-8"), query
    else:
        body, query_string = data, {**query, "query": sql}
    headers = {"X-ClickHouse-User": cfg.user, "X-ClickHouse-Key": cfg.password}
    for attempt in range(1, _RETRIES + 1):
        try:
            response = _session().post(cfg.url, params=query_string, data=body, stream=stream, timeout=timeout,
                                       headers=headers)
            break
        except (requests.ConnectionError, requests.Timeout):
            if attempt == _RETRIES:
                raise
            time.sleep(min(2 ** attempt, 30))
    if response.status_code != 200:
        raise RuntimeError(f"ClickHouse error {response.status_code}: {response.text[:2000]}")
    return response


def _insert_partition(cfg: ClickHouse, table: str, lines: Iterable[str], batch_size: int) -> int:
    sql = f"INSERT INTO {table} FORMAT JSONEachRow"
    buffer: list[str] = []
    written = 0
    for line in lines:
        buffer.append(line)
        if len(buffer) >= batch_size:
            _post(cfg, sql, data="\n".join(buffer).encode("utf-8"), settings=_INSERT_SETTINGS)
            written += len(buffer)
            buffer.clear()
    if buffer:
        _post(cfg, sql, data="\n".join(buffer).encode("utf-8"), settings=_INSERT_SETTINGS)
        written += len(buffer)
    return written


class ClickHouseClient:
    def __init__(self, cfg: ClickHouse | None = None, scratch_dir: str | None = None) -> None:
        self.cfg = cfg or ClickHouse()
        self.scratch_dir = scratch_dir or tempfile.mkdtemp(prefix="studentsdw-ch-")

    def execute(self, sql: str, params: Mapping[str, Any] | None = None) -> str:
        return _post(self.cfg, sql, params=params).text

    def query(self, sql: str, params: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
        text = _post(self.cfg, f"{sql}\nFORMAT JSONEachRow", params=params).text
        return [json.loads(line) for line in text.splitlines() if line.strip()]

    def scalar(self, sql: str, params: Mapping[str, Any] | None = None) -> Any:
        rows = self.query(sql, params)
        return next(iter(rows[0].values())) if rows else None

    def insert_rows(self, table: str, rows: Iterable[Mapping[str, Any]], batch_size: int = 20_000) -> int:
        lines = (json.dumps(row, default=str, ensure_ascii=False) for row in rows)
        return _insert_partition(self.cfg, table, lines, batch_size)

    def table_columns(self, table: str) -> list[str]:
        rows = self.query(
            "SELECT name FROM system.columns WHERE database = currentDatabase() AND table = {t:String} "
            "AND default_kind NOT IN ('MATERIALIZED', 'ALIAS') ORDER BY position", {"t": table})
        return [r["name"] for r in rows]

    def insert_dataframe(self, df, table: str, batch_size: int = 50_000) -> int:
        from pyspark.sql import functions as F
        from pyspark.sql.types import BooleanType

        columns = set(self.table_columns(table))
        selected = [F.col(f.name).cast("int").alias(f.name) if isinstance(f.dataType, BooleanType) else F.col(f.name)
                    for f in df.schema.fields if f.name in columns]
        payload = df.select(*selected)
        accumulator = df.sparkSession.sparkContext.accumulator(0)
        cfg = self.cfg

        def write(lines: Iterable[str]) -> None:
            accumulator.add(_insert_partition(cfg, table, lines, batch_size))

        payload.toJSON().foreachPartition(write)
        return int(accumulator.value)

    def read_dataframe(self, spark, sql: str, params: Mapping[str, Any] | None = None):
        path = os.path.join(self.scratch_dir, f"{uuid.uuid4().hex}.parquet")
        response = _post(self.cfg, f"{sql}\nFORMAT Parquet", params=params, stream=True,
                         settings={"output_format_parquet_string_as_string": "1"})
        with open(path, "wb") as handle:
            for chunk in response.iter_content(chunk_size=1 << 20):
                handle.write(chunk)
        return spark.read.parquet(path)

    def clear_scratch(self) -> None:
        for name in os.listdir(self.scratch_dir):
            try:
                os.remove(os.path.join(self.scratch_dir, name))
            except OSError:
                pass

    def stage_keys(self, keys_df, key_column: str, event_column: str | None = None, event_ms: int | None = None) -> str:
        from pyspark.sql import functions as F

        work_id = uuid.uuid4().hex
        event = F.col(event_column) if event_column else F.lit(event_ms)
        frame = keys_df.select(F.lit(work_id).alias("work_id"),
                               F.col(key_column).cast("long").alias("key_value"),
                               event.cast("long").alias("event_ms"))
        self.insert_dataframe(frame, "etl_work_keys")
        return work_id

    def copy_rows(self, table: str, key_column: str, work_id: str, overrides: Mapping[str, str],
                  extra_where: str = "1") -> None:
        columns = self.table_columns(table)
        select = ", ".join(f"{overrides[c]} AS {c}" if c in overrides else f"t.{c} AS {c}" for c in columns)
        self.execute(
            f"INSERT INTO {table} ({', '.join(columns)}) "
            f"SELECT {select} FROM {table} AS t FINAL "
            f"INNER JOIN (SELECT key_value, max(event_ms) AS event_ms FROM etl_work_keys "
            f"            WHERE work_id = {{w:String}} GROUP BY key_value) AS w ON w.key_value = t.{key_column} "
            f"WHERE {extra_where}",
            {"w": work_id})
