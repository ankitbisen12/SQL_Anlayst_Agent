import atexit
import datetime as dt
import logging
import threading
import time
import uuid
from decimal import Decimal
from typing import Any

from psycopg import sql
from psycopg_pool import ConnectionPool

from utils.config import get_settings

logger = logging.getLogger(__name__)

_pool: ConnectionPool | None = None
_pool_lock = threading.Lock()

_schema_cache: dict[str, tuple[float, str]] = {}
_schema_lock = threading.Lock()


def get_pool() -> ConnectionPool:
    """Lazily create a single process-wide connection pool (re-used by every request)."""
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                settings = get_settings()
                _pool = ConnectionPool(
                    conninfo=settings.database_url,
                    min_size=settings.db_pool_min_size,
                    max_size=settings.db_pool_max_size,
                    # prepare_threshold=None: no server-side prepared statements, so the pool also works
                    # behind transaction poolers (Supabase Supavisor :6543, PgBouncer, Neon pooler).
                    kwargs={"application_name": "sql-analyst-agent", "prepare_threshold": None},
                    # Cloud poolers drop idle connections: validate before handing one out.
                    check=ConnectionPool.check_connection,
                    max_idle=300,
                    open=True,
                )
                atexit.register(close_pool)
    return _pool


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


def _to_json_safe(value: Any) -> Any:
    """Convert Postgres values into JSON-serialisable Python values."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (dt.datetime, dt.date, dt.time)):
        return value.isoformat()
    if isinstance(value, dt.timedelta):
        return value.total_seconds()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (list, tuple)):
        return [_to_json_safe(v) for v in value]
    if isinstance(value, dict):
        return {k: _to_json_safe(v) for k, v in value.items()}
    return str(value)


class DatabaseUtil:
    """
    Read-only access to the analytics database.

    Safety layers applied here (in addition to the SQL guardrails):
      * every query runs inside a READ ONLY transaction which is always rolled back
      * a per-statement timeout protects the database from expensive queries
      * the number of fetched rows is capped
    """

    def __init__(self, pool: ConnectionPool | None = None):
        self.pool = pool or get_pool()
        self.settings = get_settings()

    def ping(self) -> bool:
        with self.pool.connection() as conn:
            conn.execute("SELECT 1")
        return True

    def execute_query(self, query: str, max_rows: int | None = None) -> dict:
        """
        Execute a (validated) SELECT query and return a structured result:
        {"columns": [...], "rows": [[...]], "row_count": int, "truncated": bool}
        """
        max_rows = max_rows or self.settings.max_row_limit
        with self.pool.connection() as conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("SET TRANSACTION READ ONLY")
                    cur.execute(
                        sql.SQL("SET LOCAL statement_timeout = {}").format(
                            sql.Literal(self.settings.db_statement_timeout_ms)
                        )
                    )
                    cur.execute(query)
                    if cur.description is None:
                        return {"columns": [], "rows": [], "row_count": 0, "truncated": False}
                    columns = [d.name for d in cur.description]
                    fetched = cur.fetchmany(max_rows + 1)
            finally:
                # Never commit anything coming from the agent.
                conn.rollback()

        truncated = len(fetched) > max_rows
        rows = [[_to_json_safe(v) for v in row] for row in fetched[:max_rows]]
        return {"columns": columns, "rows": rows, "row_count": len(rows), "truncated": truncated}

    def schema_details(self, schema: str = "public", sample_rows: int = 3) -> str:
        """
        Return a compact, LLM-friendly description of the schema: tables, columns, types,
        foreign keys and a few sample rows. Sensitive columns are hidden from the LLM.
        The result is cached (SCHEMA_CACHE_TTL_SECONDS) because the schema rarely changes
        and introspection is the most expensive part of building the prompt.
        """
        ttl = self.settings.schema_cache_ttl_seconds
        with _schema_lock:
            cached = _schema_cache.get(schema)
            if cached and time.time() - cached[0] < ttl:
                return cached[1]

        description = self._build_schema_description(schema, sample_rows)
        with _schema_lock:
            _schema_cache[schema] = (time.time(), description)
        return description

    def _build_schema_description(self, schema: str, sample_rows: int) -> str:
        sensitive = self.settings.sensitive_column_set
        with self.pool.connection() as conn:
            columns = conn.execute(
                """
                SELECT c.table_name, c.column_name, c.data_type
                FROM information_schema.columns c
                JOIN information_schema.tables t
                  ON t.table_schema = c.table_schema AND t.table_name = c.table_name
                WHERE c.table_schema = %s AND t.table_type IN ('BASE TABLE', 'VIEW')
                ORDER BY c.table_name, c.ordinal_position
                """,
                (schema,),
            ).fetchall()

            foreign_keys = conn.execute(
                """
                SELECT conrelid::regclass::text, pg_get_constraintdef(oid)
                FROM pg_constraint
                WHERE contype = 'f' AND connamespace = %s::regnamespace
                ORDER BY 1
                """,
                (schema,),
            ).fetchall()

            tables: dict[str, list[tuple[str, str]]] = {}
            for table, column, data_type in columns:
                if column.lower() in sensitive:
                    continue
                tables.setdefault(table, []).append((column, data_type))

            parts: list[str] = []
            for table, cols in tables.items():
                col_lines = "\n".join(f"    - {name} ({dtype})" for name, dtype in cols)
                parts.append(f"Table: {table}\n  Columns:\n{col_lines}")
                try:
                    query = sql.SQL("SELECT {} FROM {}.{} LIMIT {}").format(
                        sql.SQL(", ").join(sql.Identifier(c) for c, _ in cols),
                        sql.Identifier(schema),
                        sql.Identifier(table),
                        sql.Literal(sample_rows),
                    )
                    rows = conn.execute(query).fetchall()
                    if rows:
                        sample = "\n".join(f"    {tuple(_to_json_safe(v) for v in r)}" for r in rows)
                        parts.append(f"  Sample rows:\n{sample}")
                except Exception as exc:  # no privilege on a table etc. -> skip samples
                    logger.warning("Could not sample table %s: %s", table, exc)
                    conn.rollback()

            if foreign_keys:
                fk_lines = "\n".join(f"  - {table}: {definition}" for table, definition in foreign_keys)
                parts.append(f"Relationships:\n{fk_lines}")

        return "\n\n".join(parts)

    @staticmethod
    def clear_schema_cache() -> None:
        with _schema_lock:
            _schema_cache.clear()
