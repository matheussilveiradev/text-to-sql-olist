"""Monta a descrição do banco que vai no prompt: DDL de cada tabela, linhas de exemplo e notas de negócio."""
from __future__ import annotations

import sqlite3
from pathlib import Path

NOTES_PATH = Path(__file__).with_name("schema_notes.md")


def _format_value(value, max_len: int = 40) -> str:
    text = "NULL" if value is None else str(value)
    return text if len(text) <= max_len else text[: max_len - 3] + "..."


def describe_schema(conn: sqlite3.Connection, sample_rows: int = 3) -> str:
    tables = conn.execute(
        "SELECT name, sql FROM sqlite_master "
        "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()

    parts: list[str] = []
    for name, ddl in tables:
        cursor = conn.execute(f'SELECT * FROM "{name}" LIMIT {int(sample_rows)}')
        columns = [d[0] for d in cursor.description]
        examples = [" | ".join(_format_value(v) for v in row) for row in cursor.fetchall()]
        parts.append(
            f"{ddl.strip()};\n"
            f"-- exemplos ({' | '.join(columns)}):\n"
            + "\n".join(f"--   {line}" for line in examples)
        )

    notes = NOTES_PATH.read_text(encoding="utf-8").strip() if NOTES_PATH.exists() else ""
    schema = "\n\n".join(parts)
    return f"{schema}\n\n# Notas sobre os dados\n{notes}" if notes else schema
