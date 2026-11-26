#!/bin/sh
set -eu

CONNECTOR=students-sqlserver-cdc

until curl -fs "$CONNECT_URL/connector-plugins" >/dev/null; do
  echo "[connect-register] waiting for Kafka Connect"
  sleep 3
done

cat > /tmp/connector.json <<EOF
{
  "connector.class": "io.debezium.connector.sqlserver.SqlServerConnector",
  "tasks.max": "1",
  "database.hostname": "mssql",
  "database.port": "1433",
  "database.user": "${ETL_SQL_USER}",
  "database.password": "${ETL_SQL_PASSWORD}",
  "database.names": "Students",
  "database.encrypt": "false",
  "database.trustServerCertificate": "true",
  "topic.prefix": "students",
  "table.include.list": "dbo.Students,dbo.CourseEnrollments,dbo.CourseOfferings,dbo.Applicants",
  "snapshot.mode": "no_data",
  "decimal.handling.mode": "string",
  "time.precision.mode": "connect",
  "tombstones.on.delete": "false",
  "poll.interval.ms": "500",
  "schema.history.internal.kafka.bootstrap.servers": "kafka:9092",
  "schema.history.internal.kafka.topic": "_schema_history.students",
  "schema.history.internal.store.only.captured.tables.ddl": "true",
  "key.converter": "org.apache.kafka.connect.json.JsonConverter",
  "key.converter.schemas.enable": "false",
  "value.converter": "org.apache.kafka.connect.json.JsonConverter",
  "value.converter.schemas.enable": "false",
  "topic.creation.default.replication.factor": "1",
  "topic.creation.default.partitions": "3"
}
EOF

curl -fsS -X PUT -H "Content-Type: application/json" \
     --data @/tmp/connector.json "$CONNECT_URL/connectors/$CONNECTOR/config" >/dev/null

for _ in $(seq 1 30); do
  state=$(curl -fs "$CONNECT_URL/connectors/$CONNECTOR/status" | sed -n 's/.*"connector":{"state":"\([A-Z]*\)".*/\1/p')
  if [ "$state" = "RUNNING" ]; then
    echo "[connect-register] connector $CONNECTOR is RUNNING"
    exit 0
  fi
  sleep 2
done
echo "[connect-register] connector did not reach RUNNING state" >&2
curl -fs "$CONNECT_URL/connectors/$CONNECTOR/status" >&2 || true
exit 1
