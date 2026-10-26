"""
Pick the best way to visualise a SQL result.

This is deliberately deterministic (no LLM call): it is free, instant and easy to test. The frontend renders
the returned spec with Recharts and always offers the raw table as well.
"""

import re

DATE_NAME_RE = re.compile(r"(date|month|year|week|day|time|period|quarter|_at$|_on$)", re.IGNORECASE)
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}(-\d{2})?([T ][\d:.]+)?")
SHARE_WORDS_RE = re.compile(r"\b(share|proportion|percent(age)?|distribution|breakdown|split|mix)\b", re.IGNORECASE)
ID_NAME_RE = re.compile(r"(^id$|_id$)", re.IGNORECASE)


def _is_numeric_column(values: list) -> bool:
    present = [v for v in values if v is not None]
    return bool(present) and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in present)


def _is_date_column(name: str, values: list) -> bool:
    present = [v for v in values if v is not None]
    if not present:
        return False
    if all(isinstance(v, str) and ISO_DATE_RE.match(v) for v in present):
        return True
    return bool(DATE_NAME_RE.search(name)) and all(isinstance(v, (str, int)) for v in present)


def suggest_chart(question: str, result: dict) -> dict:
    columns: list[str] = result.get("columns", [])
    rows: list[list] = result.get("rows", [])

    if not rows or not columns:
        return {"type": "none"}

    if len(rows) == 1 and len(columns) == 1:
        return {"type": "metric", "label": columns[0], "value": rows[0][0]}

    col_values = {c: [r[i] for r in rows] for i, c in enumerate(columns)}
    date_cols = [c for c in columns if _is_date_column(c, col_values[c])]
    numeric_cols = [
        c for c in columns
        if c not in date_cols and _is_numeric_column(col_values[c]) and not ID_NAME_RE.search(c)
    ]
    category_cols = [c for c in columns if c not in numeric_cols and c not in date_cols]

    if date_cols and numeric_cols and len(rows) >= 2:
        return {"type": "line", "x": date_cols[0], "y": numeric_cols[:3]}

    if category_cols and numeric_cols and 2 <= len(rows) <= 30:
        if SHARE_WORDS_RE.search(question or "") and len(rows) <= 8 and len(numeric_cols) >= 1:
            return {"type": "pie", "x": category_cols[0], "y": numeric_cols[:1]}
        return {"type": "bar", "x": category_cols[0], "y": numeric_cols[:3]}

    if len(numeric_cols) >= 2 and not category_cols and len(rows) >= 3:
        return {"type": "scatter", "x": numeric_cols[0], "y": numeric_cols[1:2]}

    return {"type": "table"}
