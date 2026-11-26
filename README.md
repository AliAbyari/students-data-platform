<p align="center"><img src="docs/brand/logo.png" width="140" alt="Students Data Platform" /></p>

<h1 align="center">Students Data Platform</h1>

<p align="center">
  End-to-end data engineering platform for a university's operational <b>Students</b> database:<br/>
  SQL Server (TPS) → Airflow + Spark → PostgreSQL staging → ClickHouse data warehouse → Grafana &amp; a bilingual .NET Blazor PWA
</p>

<p align="center">
  <img alt="SQL Server" src="https://img.shields.io/badge/SQL%20Server-2022-CC2927?logo=microsoftsqlserver&logoColor=white" />
  <img alt="Airflow" src="https://img.shields.io/badge/Airflow-2.10-017CEE?logo=apacheairflow&logoColor=white" />
  <img alt="Spark" src="https://img.shields.io/badge/Spark-3.5-E25A1C?logo=apachespark&logoColor=white" />
  <img alt="Kafka" src="https://img.shields.io/badge/Kafka-3.9-231F20?logo=apachekafka&logoColor=white" />
  <img alt="Debezium" src="https://img.shields.io/badge/Debezium-2.7-91D443" />
  <img alt="PostgreSQL" src="https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white" />
  <img alt="ClickHouse" src="https://img.shields.io/badge/ClickHouse-24.8-FFCC01?logo=clickhouse&logoColor=black" />
  <img alt="Grafana" src="https://img.shields.io/badge/Grafana-11-F46800?logo=grafana&logoColor=white" />
  <img alt=".NET" src="https://img.shields.io/badge/.NET%2010-Blazor%20PWA-512BD4?logo=dotnet&logoColor=white" />
  <img alt="Docker" src="https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white" />
</p>

---

## Overview

The platform moves data from an operational (transactional) SQL Server database into a ClickHouse
data warehouse built on a Kimball dimensional model, and implements the **transformation layer in two
independent ways**:

| Path | Flow | What it does |
|---|---|---|
| **Batch + SCD** | SQL Server → Airflow + Spark → PostgreSQL (staging) → Spark → ClickHouse | Scheduled full extract, hash-based change detection, **SCD Type 1 and Type 2** dimensions, incremental fact loads, data quality rules and staging-to-warehouse reconciliation |
| **Near real-time + CDC** | SQL Server CDC → Debezium → Kafka → Spark Structured Streaming → ClickHouse | Log-based change data capture; every insert, update or delete reaches the warehouse in **about 5 seconds**, applying the same SCD logic as the batch path |

Both paths share one transformation library (`studentsdw`), so a change is modelled identically whether
it arrives through the nightly batch or the stream. The presentation layer consists of **Grafana** dashboards
and the **Students Portal**, a bilingual (English / Persian) **.NET 10 Blazor WebAssembly PWA** that performs
CRUD on SQL Server (producing the changes that CDC carries) and reports from ClickHouse.

### Highlights

- **Kimball dimensional model**: surrogate keys, special members (Unknown / Not applicable), conformed and junk dimensions, transaction and snapshot facts, semantic views (`v_*`, `rpt_*`).
- **SCD Type 2 with Type 1 corrections**: a changed city or status creates a new version and closes the previous one; a name correction is applied to every historical version without creating one.
- **Correct ordering between paths**: every row carries a version taken from the source commit time, so a late batch never overwrites a newer CDC change (ClickHouse `ReplacingMergeTree`).
- **Idempotent loads**: re-running a batch writes no duplicate rows; soft deletes keep history.
- **Data quality**: 15 rules on the staging data plus row-count reconciliation per batch, visible in the portal and Grafana.
- **Observability**: Prometheus with exporters for the host, containers, Kafka, PostgreSQL and ClickHouse; service probes and alert rules; eight provisioned Grafana dashboards.
- **Students Portal**: JWT sign-in with roles, SCD2 history per student, live CDC monitor with end-to-end latency, pipeline and data quality view, Jalali calendar, light / dark themes, installable PWA, built-in guide (<kbd>?</kbd> or <kbd>F1</kbd>).
- **One-command start** on Windows, WSL and Linux; the database backup is bundled in the repository.

---

## Architecture

```mermaid
flowchart LR
    subgraph TPS["Data source · TPS"]
        SQL[(SQL Server<br/>Students)]
    end
    subgraph BATCH["Batch path · SCD"]
        AF[Airflow DAG<br/>students_batch_scd] --> SX[Spark extract]
        SX --> PG[(PostgreSQL<br/>stg / control)]
        PG --> ST[Spark transform<br/>SCD1 · SCD2 · incremental facts]
    end
    subgraph STREAM["Near real-time path · CDC"]
        DBZ[Debezium<br/>Kafka Connect] --> KF[(Kafka)]
        KF --> SS[Spark Structured<br/>Streaming]
    end
    subgraph DW["Data warehouse · OLAP"]
        CH[(ClickHouse<br/>students_dw)]
    end
    subgraph UI["Presentation"]
        GF[Grafana]
        BZ[Blazor PWA<br/>EN / FA]
    end
    SQL --> SX
    SQL -- CDC log --> DBZ
    ST --> CH
    SS --> CH
    CH --> GF
    CH --> BZ
    BZ -- CRUD --> SQL
```

| Layer | Technology | Role |
|---|---|---|
| Data source (relational, operational) | SQL Server 2022 | `Students` database, restored automatically from the bundled backup; CDC enabled on the four most volatile tables |
| Staging | PostgreSQL 16 | `stg.*` raw copy of each batch, `control.*` batch registry and surrogate key sequences |
| Orchestration | Apache Airflow 2.10 | DAG `students_batch_scd`: register → extract → validate → dimensions → facts → reconcile → close |
| Processing | Apache Spark 3.5 | PySpark batch jobs and Structured Streaming, sharing the `studentsdw` library |
| Streaming | Debezium 2.7 + Kafka 3.9 (KRaft) | Log-based change data capture |
| Data warehouse / OLAP | ClickHouse 24.8 | Kimball star schema and semantic layer |
| Monitoring | Prometheus + exporters | Host, container, Kafka and database metrics, probes and alerts |
| Presentation | Grafana 11 · Blazor WebAssembly (.NET 10) | Dashboards and the bilingual PWA |

Design details (Inmon properties, Kimball model, SCD and CDC implementation) are in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

---

## Quick start

**Requirements:** Git and Docker only. Give Docker at least **8 GB of RAM** and keep about 15 GB of disk free.

| Environment | Docker |
|---|---|
| Windows | [Docker Desktop](https://www.docker.com/products/docker-desktop/) with the WSL 2 backend (Linux containers) |
| WSL | Docker Desktop with **Settings → Resources → WSL Integration** enabled for the distro, or Docker Engine installed inside WSL |
| Linux | Docker Engine with the Compose v2 plugin |

**1. Get the project.** The `Students` database backup ships inside the repository; nothing else to download.

```bash
git clone https://github.com/AliAbyari/students-data-platform.git
```

**2. Start it.**

- **Windows:** double-click `start.bat` in the `students-data-platform` folder.
- **Linux / WSL:**
  ```bash
  cd students-data-platform && ./start.sh
  ```

The start script takes care of everything:
- checks Docker and starts Docker Desktop (or the Docker service) when it is not running
- uses Docker Hub when reachable and falls back to a mirror when it is not (HTTP 403 in some regions)
- unpacks the database backup and checks that the required ports are free
- builds and starts every service, then opens the portal in the browser

The first run takes 10–20 minutes (image builds, database restore, CDC setup and the initial warehouse load,
which Airflow starts automatically). Later starts take under two minutes. Double-clicking `start.bat` also works
for a checkout inside the WSL file system; it hands over to `start.sh` in that distro.

| Service | URL | Default credentials (`.env`) |
|---|---|---|
| Students Portal (Blazor PWA) | http://localhost:9080 | `admin` / `Portal#Admin2026` |
| Airflow | http://localhost:8090 | `admin` / `Airflow#2026` |
| Grafana | http://localhost:3000 | `admin` / `Grafana#2026` |
| Kafka UI | http://localhost:8082 | — |
| Prometheus | http://localhost:9091 | — |
| ClickHouse HTTP / Play | http://localhost:8123/play | `dw` / `Dw_ClickHouse#2026` |
| SQL Server | `localhost,14330` | `sa` / `Sa_Students#2026` |
| PostgreSQL | `localhost:5433` | `platform` / `Platform#2026` |

Stop with `stop.bat` or `./stop.sh`; add `--reset` to delete all volumes and start from scratch next time.

---

## Try it

1. **Batch load**: open the `students_batch_scd` DAG in Airflow. When it finishes, the portal's *Pipelines & quality* page shows every step and the data quality results.
2. **Live CDC**: in the portal open *Students*, pick a student and change the city or status.
3. **SCD Type 2**: open that student's *History*. Within seconds a new version appears in `dim_student`; the previous one is closed with `valid_to`.
4. **SCD Type 1**: correct the student's name. The correction is applied to every historical version and creates no new one.
5. **Incremental facts**: record a grade in *Enrollments*; the term and cumulative GPA on the history page update.
6. **Monitoring**: the *Live CDC* page and the *Students DW — CDC & Pipelines* dashboard show event counts and end-to-end latency. Stop Kafka with `docker compose stop kafka` and the *Platform Health* dashboard turns it red within seconds.

---

## Screenshots

### Airflow

Batch DAG `students_batch_scd`: register the batch, extract to PostgreSQL staging with Spark, validate, load the
dimensions (SCD1 / SCD2) and facts into ClickHouse, reconcile row counts and close the batch.

<p align="center">
  <img src="docs/screenshots/airflow-graph.png" alt="Airflow DAG graph" />
</p>
<p align="center">
  <img src="docs/screenshots/airflow-dags.png" width="80%" alt="Airflow DAG list" />
</p>

### Kafka UI · Debezium

Change topics produced by the Debezium SQL Server connector, and the connector itself.

<p align="center">
  <img src="docs/screenshots/kafka-ui-connectors.png" width="49%" alt="Kafka Connect connectors" />
  <img src="docs/screenshots/kafka-ui-topics.png" width="49%" alt="Kafka topics" />
</p>

### ClickHouse

SCD Type 2 history of one student in the warehouse: the first version comes from the batch load, the following
versions from CDC events, each closed by the next one.

<p align="center">
  <img src="docs/screenshots/clickhouse-play.png" alt="ClickHouse Play query of dim_student history" />
</p>

### Prometheus

<p align="center">
  <img src="docs/screenshots/prometheus-targets.png" width="80%" alt="Prometheus targets" />
</p>

### Grafana

| Students DW — Overview | Students DW — CDC & Pipelines |
|---|---|
| <img src="docs/screenshots/grafana-students-dw-overview.png" alt="Overview dashboard" /> | <img src="docs/screenshots/grafana-students-dw-operations.png" alt="CDC and pipelines dashboard" /> |
| **Students DW — Insights** | **ClickHouse — Warehouse Internals** |
| <img src="docs/screenshots/grafana-students-dw-insights.png" alt="Insights dashboard" /> | <img src="docs/screenshots/grafana-clickhouse-internals.png" alt="ClickHouse internals dashboard" /> |
| **Platform Health — Service Status** | **Kafka & CDC Streaming** |
| <img src="docs/screenshots/grafana-platform-health.png" alt="Platform health dashboard" /> | <img src="docs/screenshots/grafana-kafka-streaming.png" alt="Kafka and CDC dashboard" /> |
| **System Load — Host & Containers** | **Databases — ClickHouse, PostgreSQL, SQL Server** |
| <img src="docs/screenshots/grafana-system-load.png" alt="System load dashboard" /> | <img src="docs/screenshots/grafana-platform-databases.png" alt="Databases dashboard" /> |

### Students Portal (.NET Blazor PWA)

| Sign in | Built-in guide (<kbd>?</kbd> / <kbd>F1</kbd>) |
|---|---|
| <img src="docs/screenshots/portal-en-login.png" alt="Sign-in page" /> | <img src="docs/screenshots/portal-en-guide.png" alt="Platform guide" /> |
| **Student history (SCD Type 2)** | **Live CDC monitor** |
| <img src="docs/screenshots/portal-en-history.png" alt="Student history" /> | <img src="docs/screenshots/portal-en-live.png" alt="Live CDC" /> |
| **Students (CRUD on SQL Server)** | **Pipelines & data quality** |
| <img src="docs/screenshots/portal-en-students.png" alt="Students" /> | <img src="docs/screenshots/portal-en-pipeline.png" alt="Pipelines" /> |

<p align="center">
  <img src="docs/screenshots/portal-en-dashboard.png" width="74%" alt="Portal dashboard" />
  <img src="docs/screenshots/portal-en-mobile.png" width="22%" alt="Portal on mobile" />
</p>

The same portal in Persian (right-to-left, Jalali calendar):

<p align="center">
  <img src="docs/screenshots/portal-fa-login.png" width="49%" alt="Sign-in page in Persian" />
  <img src="docs/screenshots/portal-fa-dashboard.png" width="49%" alt="Dashboard in Persian" />
</p>

---

## Project structure

```
students-data-platform/
├── docker-compose.yml          all services, dependencies and health checks
├── start.bat / start.sh        one-command start (Windows / Linux and WSL)
├── data/Students.bak.tar.gz.*  compressed database backup in 5 parts (joined and unpacked automatically)
├── infra/
│   ├── sqlserver/              backup restore, CDC enablement, least-privilege logins
│   ├── postgres/               staging and control schemas
│   ├── clickhouse/ddl/         dimensions, facts, operational metadata, semantic layer, special members
│   ├── debezium/               connector registration
│   ├── grafana/                provisioned data sources and dashboards (warehouse + monitoring)
│   └── monitoring/             Prometheus, alert rules, blackbox probes, docker exporter
├── pipelines/
│   ├── airflow/                image and DAG
│   ├── spark/lib/studentsdw/   transformation library shared by batch and stream (SCD, facts, data quality)
│   └── spark/jobs/             extract_to_staging · load_warehouse · stream_cdc
├── app/                        Students Portal: ASP.NET Core API + Blazor WebAssembly PWA
└── docs/                       architecture notes, screenshots, brand assets
```

---

## Troubleshooting

| Problem | Cause and fix |
|---|---|
| `403 Forbidden` while pulling images | Docker Hub refuses some networks. With the default `DOCKERHUB_MIRROR=auto` the start script picks Docker Hub or the `docker.arvancloud.ir` mirror; set it explicitly in `.env` to override |
| `Docker was not found` in WSL | Enable Docker Desktop → Settings → Resources → WSL Integration for the distro, or install Docker Engine inside WSL |
| `permission denied` on the Docker socket (Linux) | Run `sudo usermod -aG docker $USER` once and open a new terminal |
| `Permission denied` running `./start.sh` | Run `bash start.sh` (a checkout made on Windows may lose the executable bit) |
| `These ports are already in use` | Another program uses a host port (for example a local SQL Server instance or another web app). The start script names the ports; change the matching `PORT_*` values in `.env` and run it again |
| `ports are not available` on Windows | Windows reserves some ports for Hyper-V (8080, hence the portal on 9080); change the `PORT_*` values in `.env` |
| Dashboards are empty | The initial Airflow load takes a few minutes; follow it in Airflow or on the portal's *Pipelines & quality* page |

---

<p align="center">
  📖 <b>مستندات فارسی:</b> <a href="README.fa.md">README.fa.md</a>
</p>
