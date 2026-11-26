from __future__ import annotations

from dataclasses import dataclass, field

from pyspark.sql import Column, DataFrame, SparkSession, Window
from pyspark.sql import functions as F

from .clickhouse import ClickHouseClient
from .control import allocate_keys

_SEPARATOR = "␟"
_NULL = "∅"


def row_hash(columns: list[str]) -> Column:
    return F.xxhash64(F.concat_ws(_SEPARATOR, *[F.coalesce(F.col(c).cast("string"), F.lit(_NULL)) for c in columns]))


def assign_keys(df: DataFrame, sequence: str, key_column: str, order_by: list[str]) -> DataFrame:
    count = df.count()
    if count == 0:
        return df.withColumn(key_column, F.lit(None).cast("long"))
    first = allocate_keys(sequence, count)
    window = Window.orderBy(*order_by)
    return df.withColumn(key_column, (F.lit(first - 1) + F.row_number().over(window)).cast("long"))


def in_filter(column: str, values: list | None, param: str = "ids", kind: str = "Int32") -> tuple[str, dict]:
    if values is None:
        return "1", {}
    return f"{column} IN {{{param}:Array({kind})}}", {param: "[" + ",".join(_sql_literal(v) for v in values) + "]"}


def _sql_literal(value) -> str:
    if isinstance(value, str):
        return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"
    return str(int(value))


@dataclass
class MergeResult:
    inserted: int = 0
    updated: int = 0
    deleted: int = 0
    details: dict = field(default_factory=dict)

    @property
    def written(self) -> int:
        return self.inserted + self.updated + self.deleted


def merge_type1(spark: SparkSession, ch: ClickHouseClient, incoming: DataFrame, *, table: str, key_column: str,
                business_key: list[str], hash_columns: list[str], batch_id: int, full_snapshot: bool,
                sequence: str | None = None, snapshot_ms: int | None = None,
                key_filter: tuple[str, dict] = ("1", {})) -> MergeResult:
    result = MergeResult()
    incoming = incoming.withColumn("row_hash", row_hash(hash_columns))
    where, params = key_filter
    existing = ch.read_dataframe(
        spark,
        f"SELECT {key_column} AS _key, {', '.join(business_key)}, row_hash AS _hash, "
        f"toInt64(row_version) AS _ver, is_deleted AS _del FROM {table} FINAL "
        f"WHERE {key_column} > 0 AND {where}", params)

    joined = incoming.join(existing, on=business_key, how="full_outer" if full_snapshot else "left").cache()
    present = joined.filter(F.col("_version").isNotNull())
    fresh = present.filter(F.col("_ver").isNull() | (F.col("_ver") < F.col("_version")))

    new_rows = fresh.filter(F.col("_key").isNull() & (F.col("_deleted") == 0))
    if sequence is not None:
        new_rows = assign_keys(new_rows.drop(key_column) if key_column in new_rows.columns else new_rows,
                               sequence, key_column, business_key)
    changed = (fresh.filter(F.col("_key").isNotNull() & (F.col("_deleted") == 0)
                            & ((F.col("_hash") != F.col("row_hash")) | (F.col("_del") == 1)))
               .withColumn(key_column, F.col("_key")))

    for frame, label in ((new_rows, "inserted"), (changed, "updated")):
        payload = (frame.withColumn("is_deleted", F.lit(0))
                        .withColumn("batch_id", F.lit(batch_id).cast("long"))
                        .withColumn("row_version", F.col("_version"))
                        .withColumn("change_source", F.col("_source")))
        setattr(result, label, ch.insert_dataframe(payload, table))

    deletes = fresh.filter(F.col("_key").isNotNull() & (F.col("_deleted") == 1) & (F.col("_del") == 0))
    if full_snapshot and snapshot_ms is not None:
        vanished = joined.filter(F.col("_version").isNull() & F.col("_key").isNotNull() & (F.col("_del") == 0)
                                 & (F.col("_ver") < F.lit(snapshot_ms)))
        deletes = deletes.select("_key", "_version").unionByName(
            vanished.select("_key", F.lit(snapshot_ms).cast("long").alias("_version")))
    result.deleted = soft_delete(ch, deletes, table, key_column, batch_id)
    joined.unpersist()
    return result


def soft_delete(ch: ClickHouseClient, keys: DataFrame, table: str, key_column: str, batch_id: int) -> int:
    keys = keys.select(F.col("_key"), F.col("_version")).dropDuplicates(["_key"])
    count = keys.count()
    if count:
        work_id = ch.stage_keys(keys, "_key", event_column="_version")
        ch.copy_rows(table, key_column, work_id, {
            "is_deleted": "toUInt8(1)",
            "row_version": "w.event_ms",
            "batch_id": f"toUInt64({int(batch_id)})",
        })
    return count


def merge_fact(spark: SparkSession, ch: ClickHouseClient, incoming: DataFrame, *, table: str, id_column: str,
               hash_columns: list[str], batch_id: int, full_snapshot: bool, snapshot_ms: int | None = None,
               preserve: list[str] | None = None, id_filter: tuple[str, dict] = ("1", {})) -> MergeResult:
    preserve = preserve or []
    result = MergeResult()
    where, params = id_filter
    old_columns = "".join(f", {c} AS _old_{c}" for c in preserve)
    existing = ch.read_dataframe(
        spark,
        f"SELECT {id_column}, row_hash AS _hash, toInt64(row_version) AS _ver, is_deleted AS _del{old_columns} "
        f"FROM {table} FINAL WHERE {where}", params)

    joined = incoming.join(existing, on=id_column, how="full_outer" if full_snapshot else "left")
    for column in preserve:
        joined = joined.withColumn(column, F.when(F.col(f"_old_{column}").isNotNull()
                                                  & (F.col(f"_old_{column}") != -1), F.col(f"_old_{column}"))
                                            .otherwise(F.col(column)))
    joined = joined.withColumn("row_hash", row_hash(hash_columns)).cache()

    present = joined.filter(F.col("_version").isNotNull())
    fresh = present.filter(F.col("_ver").isNull() | (F.col("_ver") < F.col("_version")))
    upserts = fresh.filter((F.col("_deleted") == 0)
                           & (F.col("_hash").isNull() | (F.col("_hash") != F.col("row_hash")) | (F.col("_del") == 1)))
    payload = (upserts.withColumn("is_deleted", F.lit(0))
                      .withColumn("batch_id", F.lit(batch_id).cast("long"))
                      .withColumn("row_version", F.col("_version"))
                      .withColumn("change_source", F.col("_source"))
                      .withColumn("loaded_at", F.current_timestamp()))
    written = ch.insert_dataframe(payload, table)
    result.details["upserted"] = written
    result.inserted = written

    deletes = fresh.filter(F.col("_hash").isNotNull() & (F.col("_deleted") == 1) & (F.col("_del") == 0)) \
                   .select(F.col(id_column).alias("_key"), "_version")
    if full_snapshot and snapshot_ms is not None:
        vanished = joined.filter(F.col("_version").isNull() & (F.col("_del") == 0)
                                 & (F.col("_ver") < F.lit(snapshot_ms)))
        deletes = deletes.unionByName(vanished.select(F.col(id_column).alias("_key"),
                                                      F.lit(snapshot_ms).cast("long").alias("_version")))
    result.deleted = soft_delete(ch, deletes, table, id_column, batch_id)
    joined.unpersist()
    return result
