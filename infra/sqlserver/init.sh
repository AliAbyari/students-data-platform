#!/usr/bin/env bash
set -euo pipefail

SQLCMD=/opt/mssql-tools18/bin/sqlcmd
run() { "$SQLCMD" -S mssql -U sa -P "$MSSQL_SA_PASSWORD" -C -b -l 10 "$@"; }
scalar() { run -h -1 -W -Q "SET NOCOUNT ON; $1" | tr -d '[:space:]'; }

step() {
  local attempt
  for attempt in 1 2 3 4 5 6; do
    run "$@" && return 0
    echo "[mssql-init] step failed (attempt ${attempt}), retrying in 10 s"
    sleep 10
  done
  return 1
}

wait_online() {
  local pending
  for _ in $(seq 1 60); do
    pending=$(scalar "SELECT COUNT(*) FROM sys.databases WHERE state_desc <> 'ONLINE' OR DATABASEPROPERTYEX(name, 'Status') <> 'ONLINE'" 2>/dev/null) || pending=""
    [[ "$pending" == "0" ]] && return 0
    sleep 5
  done
  echo "[mssql-init] WARNING: databases are still recovering, continuing with retries" >&2
}

echo "[mssql-init] waiting for SQL Server"
for _ in $(seq 1 60); do
  run -Q "SELECT 1" >/dev/null 2>&1 && break
  sleep 5
done
wait_online

if [[ "$(scalar "SELECT COUNT(*) FROM sys.databases WHERE name = 'Students'")" == "0" ]]; then
  if [[ ! -f /backup/Students.bak ]]; then
    echo "[mssql-init] ERROR: data/Students.bak was not found on the host." >&2
    exit 1
  fi
  echo "[mssql-init] restoring Students from backup (this takes a few minutes)"
  run -i /init/01_restore.sql
  wait_online
else
  echo "[mssql-init] Students database already present - restore skipped"
fi

echo "[mssql-init] enabling change data capture"
step -i /init/02_enable_cdc.sql

echo "[mssql-init] provisioning portal database"
step -i /init/03_portal_db.sql

echo "[mssql-init] provisioning service logins"
step -i /init/04_logins.sql \
  -v EtlUser="$ETL_SQL_USER" EtlPassword="$ETL_SQL_PASSWORD" \
     AppUser="$APP_SQL_USER" AppPassword="$APP_SQL_PASSWORD"

echo "[mssql-init] completed"
