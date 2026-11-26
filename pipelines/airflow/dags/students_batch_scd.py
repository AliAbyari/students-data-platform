from __future__ import annotations

import os
from datetime import timedelta

import pendulum
from airflow.decorators import dag, task
from airflow.operators.bash import BashOperator

JOBS = "/opt/pipelines/spark/jobs"
SPARK_SUBMIT = (
    "spark-submit --master \"${SPARK_MASTER:-local[*]}\" --driver-memory ${SPARK_DRIVER_MEMORY:-2g} "
    "--conf spark.sql.session.timeZone=UTC"
)


def _mark_failed(context) -> None:
    from studentsdw.control import finish_batch

    batch = context["ti"].xcom_pull(task_ids="register_batch")
    if batch:
        finish_batch(batch["batch_id"], "failed", str(context.get("exception"))[:1000])


@dag(
    dag_id="students_batch_scd",
    description="SQL Server -> PostgreSQL staging -> ClickHouse (SCD1/SCD2, incremental facts)",
    schedule=os.getenv("BATCH_SCHEDULE", "0 2 * * *"),
    start_date=pendulum.datetime(2026, 1, 1, tz="Asia/Tehran"),
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 1, "retry_delay": timedelta(minutes=2), "on_failure_callback": _mark_failed},
    tags=["students", "batch", "scd"],
)
def students_batch_scd():
    @task
    def register_batch() -> dict:
        from studentsdw.control import start_batch

        batch_id, snapshot_ms = start_batch("batch_scd")
        return {"batch_id": batch_id, "snapshot_ms": snapshot_ms}

    batch = register_batch()
    batch_id = "{{ ti.xcom_pull(task_ids='register_batch')['batch_id'] }}"
    snapshot = "{{ ti.xcom_pull(task_ids='register_batch')['snapshot_ms'] }}"

    extract = BashOperator(
        task_id="extract_to_staging",
        bash_command=f"{SPARK_SUBMIT} {JOBS}/extract_to_staging.py --batch-id {batch_id}",
        execution_timeout=timedelta(minutes=45),
    )

    @task
    def validate_staging(batch: dict) -> int:
        from studentsdw.clickhouse import ClickHouseClient
        from studentsdw.quality import run_rules

        results = run_rules(ClickHouseClient(), batch["batch_id"])
        return sum(1 for r in results if not r["passed"])

    load_dimensions = BashOperator(
        task_id="load_dimensions",
        bash_command=f"{SPARK_SUBMIT} {JOBS}/load_warehouse.py --stage dimensions "
                     f"--batch-id {batch_id} --snapshot-ms {snapshot}",
        execution_timeout=timedelta(minutes=45),
    )

    load_facts = BashOperator(
        task_id="load_facts",
        bash_command=f"{SPARK_SUBMIT} {JOBS}/load_warehouse.py --stage facts "
                     f"--batch-id {batch_id} --snapshot-ms {snapshot}",
        execution_timeout=timedelta(minutes=60),
    )

    @task
    def reconcile(batch: dict) -> list[dict]:
        from studentsdw.clickhouse import ClickHouseClient
        from studentsdw.quality import reconcile as run

        return run(ClickHouseClient(), batch["batch_id"])

    @task
    def close_batch(batch: dict) -> None:
        from studentsdw.control import finish_batch

        finish_batch(batch["batch_id"], "success")

    batch >> extract >> validate_staging(batch) >> load_dimensions >> load_facts >> reconcile(batch) \
        >> close_batch(batch)


students_batch_scd()
