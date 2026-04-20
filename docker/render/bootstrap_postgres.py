import os
import sys

from psycopg import connect, sql


DEFAULT_DATABASES = [
    "ADMINPORTAL",
    "DECISIONAPP",
    "UNITYGAMEPLAY",
    "BETTORS",
    "BETTORANALYTICS",
    "CLIENTBETDATA",
    "ODDSGENERATOR",
    "DEMOMONEY",
]


def env(name: str, default: str = "") -> str:
    return (os.getenv(name, default) or "").strip()


def required(name: str) -> str:
    value = env(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def parse_database_names() -> list[str]:
    raw = env("RENDER_REQUIRED_DATABASES", ",".join(DEFAULT_DATABASES))
    return [item.strip() for item in raw.split(",") if item.strip()]


def main() -> int:
    if env("BOOTSTRAP_RENDER_DATABASES", "1").lower() in {"0", "false", "no", "off"}:
        print("Skipping Postgres bootstrap because BOOTSTRAP_RENDER_DATABASES is disabled.")
        return 0

    host = required("BOOTSTRAP_DB_HOST")
    port = env("BOOTSTRAP_DB_PORT", "5432")
    user = required("BOOTSTRAP_DB_USER")
    password = required("BOOTSTRAP_DB_PASSWORD")
    database = env("BOOTSTRAP_DB_NAME", "postgres")
    required_databases = parse_database_names()

    print(
        f"Ensuring logical databases exist on {host}:{port} via bootstrap database {database}: "
        + ", ".join(required_databases)
    )

    with connect(
        host=host,
        port=port,
        user=user,
        password=password,
        dbname=database,
        autocommit=True,
    ) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT datname FROM pg_database")
            existing = {row[0] for row in cursor.fetchall()}

            for db_name in required_databases:
                if db_name in existing:
                    print(f"Database already exists: {db_name}")
                    continue
                cursor.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db_name)))
                print(f"Created database: {db_name}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Postgres bootstrap failed: {exc}", file=sys.stderr)
        raise
