"""
Deterministic SQL guardrail.

The LLM judge in the agent is a useful second opinion, but an LLM can be tricked. This module is the
authoritative check: it parses the generated SQL with sqlglot and only lets through a single, read-only
SELECT statement. It fails closed - anything it cannot parse is rejected.
"""

import logging
import re
from dataclasses import dataclass

import sqlglot
from sqlglot import exp

from utils.config import get_settings

logging.getLogger("sqlglot").setLevel(logging.ERROR)

# Statement / clause types that can modify data, schema, permissions or session state.
FORBIDDEN_NODES: tuple[type[exp.Expression], ...] = (
    exp.Insert, exp.Update, exp.Delete, exp.Merge, exp.Drop, exp.Create, exp.Alter,
    exp.TruncateTable, exp.Command, exp.Into, exp.Lock, exp.Copy, exp.Set, exp.Transaction,
    exp.Commit, exp.Rollback, exp.Grant, exp.Revoke, exp.Analyze, exp.Use, exp.Pragma,
    exp.Kill, exp.Refresh, exp.Cache, exp.Uncache, exp.LoadData, exp.Comment,
)

# Functions that touch the file system, sleep, change settings, run dynamic SQL or have side effects.
FORBIDDEN_FUNCTIONS = {
    "pg_sleep", "pg_sleep_for", "pg_sleep_until", "pg_read_file", "pg_read_binary_file",
    "pg_ls_dir", "pg_stat_file", "pg_ls_logdir", "pg_ls_waldir", "pg_ls_tmpdir",
    "lo_import", "lo_export", "lo_get", "lo_put", "lo_unlink", "lo_create", "lo_from_bytea",
    "dblink", "dblink_exec", "dblink_connect", "set_config", "current_setting",
    "pg_terminate_backend", "pg_cancel_backend", "pg_reload_conf", "pg_rotate_logfile",
    "query_to_xml", "query_to_xml_and_xmlschema", "query_to_xmlschema", "cursor_to_xml",
    "table_to_xml", "database_to_xml", "schema_to_xml", "nextval", "setval",
    "pg_advisory_lock", "pg_advisory_xact_lock", "pg_try_advisory_lock",
    "txid_current", "pg_current_xact_id", "pg_switch_wal", "pg_create_restore_point",
    "pg_logical_emit_message", "pg_notify",
}

FORBIDDEN_SCHEMAS = {"pg_catalog", "information_schema", "pg_toast"}

_FENCE_RE = re.compile(r"^```(?:sql|postgresql|postgres)?\s*|\s*```$", re.IGNORECASE)


@dataclass
class SQLGuardResult:
    is_safe: bool
    reason: str
    sql: str = ""


def clean_sql(raw: str) -> str:
    """Strip markdown fences, whitespace and trailing semicolons that LLMs often add."""
    text = (raw or "").strip()
    text = _FENCE_RE.sub("", text).strip()
    return text.rstrip(";").strip()


def _function_name(node: exp.Func) -> str:
    return (node.name if isinstance(node, exp.Anonymous) else node.sql_name()).lower()


def _enforce_limit(root: exp.Expression, default_limit: int, max_limit: int) -> tuple[exp.Expression, bool]:
    """Make sure the outermost query has a LIMIT no larger than max_limit. Returns (tree, changed)."""
    limit = root.args.get("limit")
    if limit is None:
        return root.limit(default_limit, copy=False), True

    value = limit.expression if isinstance(limit, exp.Limit) else None
    if isinstance(value, exp.Literal) and value.is_int and int(value.this) <= max_limit:
        return root, False
    return root.limit(max_limit, copy=False), True


def validate_sql(raw_sql: str) -> SQLGuardResult:
    """Returns true or false."""
    settings = get_settings()
    query = clean_sql(raw_sql)
    if not query:
        return SQLGuardResult(False, "The generated SQL query is empty.")

    try:
        statements = [s for s in sqlglot.parse(query, read="postgres") if s is not None]
    except sqlglot.errors.ParseError as exc:
        return SQLGuardResult(False, f"The SQL query could not be parsed safely: {str(exc).splitlines()[0]}")

    if len(statements) != 1:
        return SQLGuardResult(False, "Only a single SQL statement is allowed.")

    root = statements[0]
    if not isinstance(root, (exp.Select, exp.SetOperation)):
        return SQLGuardResult(False, f"Only SELECT queries are allowed (got {root.key.upper()}).")

    sensitive = settings.sensitive_column_set
    for node in root.walk():
        if isinstance(node, FORBIDDEN_NODES):
            return SQLGuardResult(False, f"The query contains a forbidden operation: {node.key.upper()}.")

        if isinstance(node, exp.Func) and _function_name(node) in FORBIDDEN_FUNCTIONS:
            return SQLGuardResult(False, f"The function '{_function_name(node)}' is not allowed.")

        if isinstance(node, exp.Table):
            schema_name = (node.db or "").lower()
            table_name = (node.name or "").lower()
            if schema_name in FORBIDDEN_SCHEMAS or table_name.startswith("pg_"):
                return SQLGuardResult(False, "Querying system catalogs is not allowed.")

        if isinstance(node, exp.Column) and node.name.lower() in sensitive:
            return SQLGuardResult(False, f"The column '{node.name}' contains sensitive data and cannot be queried.")

    root, changed = _enforce_limit(root, settings.max_row_limit, settings.max_row_limit)
    final_sql = root.sql(dialect="postgres") if changed else query
    return SQLGuardResult(True, "The query is a single read-only SELECT statement.", final_sql)
