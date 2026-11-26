from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if value is None:
        raise RuntimeError(f"Environment variable {name} is required.")
    return value


@dataclass(frozen=True)
class SqlServer:
    host: str = field(default_factory=lambda: _env("MSSQL_HOST", "mssql"))
    port: str = field(default_factory=lambda: _env("MSSQL_PORT", "1433"))
    database: str = field(default_factory=lambda: _env("MSSQL_DATABASE", "Students"))
    user: str = field(default_factory=lambda: _env("ETL_SQL_USER"))
    password: str = field(default_factory=lambda: _env("ETL_SQL_PASSWORD"))

    @property
    def jdbc_url(self) -> str:
        return (f"jdbc:sqlserver://{self.host}:{self.port};databaseName={self.database};"
                "encrypt=false;trustServerCertificate=true;applicationName=studentsdw-batch")


@dataclass(frozen=True)
class Postgres:
    host: str = field(default_factory=lambda: _env("PG_HOST", "postgres"))
    port: str = field(default_factory=lambda: _env("PG_PORT", "5432"))
    database: str = field(default_factory=lambda: _env("PG_DATABASE", "platform"))
    user: str = field(default_factory=lambda: _env("PG_USER"))
    password: str = field(default_factory=lambda: _env("PG_PASSWORD"))

    @property
    def jdbc_url(self) -> str:
        return f"jdbc:postgresql://{self.host}:{self.port}/{self.database}?reWriteBatchedInserts=true"

    def dsn(self) -> dict[str, str]:
        return {"host": self.host, "port": self.port, "dbname": self.database,
                "user": self.user, "password": self.password}


@dataclass(frozen=True)
class ClickHouse:
    host: str = field(default_factory=lambda: _env("CH_HOST", "clickhouse"))
    port: str = field(default_factory=lambda: _env("CH_HTTP_PORT", "8123"))
    database: str = field(default_factory=lambda: _env("CH_DATABASE", "students_dw"))
    user: str = field(default_factory=lambda: _env("CH_USER"))
    password: str = field(default_factory=lambda: _env("CH_PASSWORD"))

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}/"
