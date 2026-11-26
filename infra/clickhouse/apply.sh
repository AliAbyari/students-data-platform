#!/usr/bin/env bash
set -euo pipefail

client() {
  clickhouse-client --host "$CH_HOST" --user "$CH_USER" --password "$CH_PASSWORD" "$@"
}

for _ in $(seq 1 60); do
  client --query "SELECT 1" >/dev/null 2>&1 && break
  sleep 2
done

client --query "CREATE DATABASE IF NOT EXISTS ${CH_DATABASE}"
for file in /init/ddl/*.sql; do
  echo "[clickhouse-init] applying $(basename "$file")"
  client --database "$CH_DATABASE" --multiquery < "$file"
done
echo "[clickhouse-init] completed"
