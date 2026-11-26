from __future__ import annotations

import os

from pyspark.sql import SparkSession


def build_session(app_name: str, extra: dict[str, str] | None = None) -> SparkSession:
    builder = (SparkSession.builder.appName(app_name)
               .master(os.getenv("SPARK_MASTER", "local[*]"))
               .config("spark.driver.memory", os.getenv("SPARK_DRIVER_MEMORY", "2g"))
               .config("spark.sql.session.timeZone", "UTC")
               .config("spark.sql.shuffle.partitions", os.getenv("SPARK_SHUFFLE_PARTITIONS", "8"))
               .config("spark.sql.adaptive.enabled", "true")
               .config("spark.ui.showConsoleProgress", "false")
               .config("spark.executorEnv.PYTHONPATH", os.getenv("PYTHONPATH", "")))
    for key, value in (extra or {}).items():
        builder = builder.config(key, value)
    spark = builder.getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    return spark
