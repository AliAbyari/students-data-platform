from __future__ import annotations

import argparse
import time

from pyspark.sql import functions as F

from studentsdw.clickhouse import ClickHouseClient
from studentsdw.config import Postgres, SqlServer
from studentsdw.control import StepLog, log_extract
from studentsdw.session import build_session
from studentsdw.sources import PARTITION_COLUMNS, SOURCE_TABLES, snake, staging_table


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-id", type=int, required=True)
    args = parser.parse_args()

    spark = build_session("studentsdw-extract-to-staging")
    source, staging, ch = SqlServer(), Postgres(), ClickHouseClient()
    source_props = {"user": source.user, "password": source.password,
                    "driver": "com.microsoft.sqlserver.jdbc.SQLServerDriver", "fetchsize": "20000"}
    staging_props = {"user": staging.user, "password": staging.password, "driver": "org.postgresql.Driver",
                     "batchsize": "20000", "truncate": "true", "stringtype": "unspecified"}

    for table, columns in SOURCE_TABLES.items():
        target = staging_table(table)
        with StepLog(ch, args.batch_id, "batch_scd", f"extract.{snake(table)}") as step:
            started = time.monotonic()
            select = ", ".join(f"[{c}]" for c in columns)
            subquery = f"(SELECT {select} FROM dbo.[{table}]) AS src"
            options = dict(source_props)
            if table in PARTITION_COLUMNS:
                key = PARTITION_COLUMNS[table]
                bounds = spark.read.jdbc(source.jdbc_url,
                                         f"(SELECT MIN([{key}]) AS lo, MAX([{key}]) AS hi FROM dbo.[{table}]) AS b",
                                         properties=source_props).first()
                if bounds and bounds["lo"] is not None:
                    options.update(partitionColumn=key, lowerBound=str(bounds["lo"]),
                                   upperBound=str(bounds["hi"]), numPartitions="4")
            frame = spark.read.format("jdbc").option("url", source.jdbc_url).option("dbtable", subquery) \
                .options(**options).load()
            frame = frame.select(*[F.col(c).alias(snake(c)) for c in columns]) \
                .withColumn("_batch_id", F.lit(args.batch_id).cast("long")) \
                .withColumn("_extracted_at", F.current_timestamp())
            frame.write.jdbc(staging.jdbc_url, target, mode="overwrite", properties=staging_props)

            rows = spark.read.jdbc(staging.jdbc_url, f"(SELECT count(*) AS n FROM {target}) AS c",
                                   properties=staging_props).first()["n"]
            step.rows_read = step.rows_written = int(rows)
            log_extract(args.batch_id, target, int(rows), int((time.monotonic() - started) * 1000))
            print(f"[extract] {table:<18} -> {target:<24} {rows:>10,} rows")

    spark.stop()


if __name__ == "__main__":
    main()
