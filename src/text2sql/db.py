"""Acesso somente leitura ao SQLite, com limite de linhas e de tempo.

A segurança não depende só do validador de texto (validator.py). Aqui há mais duas camadas:
1. o arquivo é aberto em modo somente leitura (mode=ro);
2. um "authorizer" do SQLite recusa qualquer operação que não seja leitura
   (INSERT, UPDATE, DELETE, PRAGMA, ATTACH etc.), mesmo que passe pelo validador.
"""
from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

_ALLOWED_ACTIONS = {
    sqlite3.SQLITE_SELECT,
    sqlite3.SQLITE_READ,
    sqlite3.SQLITE_FUNCTION,
    getattr(sqlite3, "SQLITE_RECURSIVE", 33),  # CTE recursiva (WITH RECURSIVE)
}


class QueryError(Exception):
    """Erro ao executar a consulta (sintaxe, coluna inexistente, tempo esgotado, operação bloqueada)."""


@dataclass
class QueryResult:
    columns: list[str]
    rows: list[tuple]
    truncated: bool
    elapsed_ms: float


def _authorizer(action, arg1, arg2, db_name, trigger):
    return sqlite3.SQLITE_OK if action in _ALLOWED_ACTIONS else sqlite3.SQLITE_DENY


def connect_readonly(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    if not path.exists():
        raise FileNotFoundError(f"Banco não encontrado em {path}. Rode scripts/build_db.py primeiro.")
    conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, check_same_thread=False)
    conn.set_authorizer(_authorizer)
    return conn


def run_query(conn: sqlite3.Connection, sql: str, max_rows: int = 200, timeout_s: float = 10.0) -> QueryResult:
    """Executa a consulta e devolve no máximo max_rows linhas."""
    start = time.perf_counter()
    deadline = start + timeout_s
    # chamado a cada N instruções da VM do SQLite; retornar 1 interrompe a consulta
    conn.set_progress_handler(lambda: 1 if time.perf_counter() > deadline else 0, 10_000)
    try:
        cursor = conn.execute(sql)
        rows = cursor.fetchmany(max_rows + 1)
        columns = [d[0] for d in cursor.description or []]
    # sqlite3.Error cobre sintaxe, "not authorized" e "interrupted"; sqlite3.Warning é o que o
    # Python 3.11 ou anterior levanta quando chegam dois comandos na mesma string
    except (sqlite3.Error, sqlite3.Warning) as exc:
        if "interrupted" in str(exc):
            raise QueryError(f"a consulta passou do limite de {timeout_s:g} s") from exc
        raise QueryError(str(exc)) from exc
    finally:
        conn.set_progress_handler(None, 0)

    truncated = len(rows) > max_rows
    return QueryResult(
        columns=columns,
        rows=rows[:max_rows],
        truncated=truncated,
        elapsed_ms=(time.perf_counter() - start) * 1000,
    )
