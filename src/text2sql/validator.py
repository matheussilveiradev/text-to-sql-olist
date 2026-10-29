"""Extrai o SQL da resposta do LLM e faz uma primeira checagem de segurança.

É a primeira camada de defesa: rejeita cedo o que claramente não é uma consulta de leitura,
com uma mensagem de erro que o próprio LLM consegue usar para se corrigir.
A barreira definitiva está em db.py (modo somente leitura + authorizer).
"""
from __future__ import annotations

import re

_FENCE = re.compile(r"```(?:sql|sqlite)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)
_STRING_LITERAL = re.compile(r"'(?:[^']|'')*'")
_LINE_COMMENT = re.compile(r"--[^\n]*")
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|attach|detach|pragma|vacuum|reindex|truncate)\b",
    re.IGNORECASE,
)


class UnsafeSQLError(ValueError):
    """A consulta não é um SELECT único e somente leitura."""


def extract_sql(text: str) -> str:
    """Pega o conteúdo do bloco ```sql``` se houver; senão, usa o texto inteiro."""
    match = _FENCE.search(text)
    return (match.group(1) if match else text).strip()


def validate_sql(sql: str) -> str:
    """Devolve o SQL limpo (sem ';' final) ou levanta UnsafeSQLError."""
    cleaned = sql.strip().rstrip(";").strip()
    if not cleaned:
        raise UnsafeSQLError("a resposta não contém nenhuma consulta SQL")

    # strings e comentários são removidos antes da checagem para evitar falsos positivos,
    # como WHERE review_comment_message LIKE '%delete%'
    code = _STRING_LITERAL.sub("''", cleaned)
    code = _BLOCK_COMMENT.sub(" ", _LINE_COMMENT.sub(" ", code))

    if ";" in code:
        raise UnsafeSQLError("envie apenas um comando SQL por vez")
    if not re.match(r"^\s*(select|with)\b", code, re.IGNORECASE):
        raise UnsafeSQLError("só são permitidas consultas que começam com SELECT ou WITH")
    forbidden = _FORBIDDEN.search(code)
    if forbidden:
        raise UnsafeSQLError(f"comando não permitido: {forbidden.group(1).upper()}")
    return cleaned
