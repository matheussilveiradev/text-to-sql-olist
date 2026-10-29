"""Agente que transforma uma pergunta em português em SQL, executa e (opcionalmente) explica o resultado.

Fluxo:
    pergunta -> LLM gera SQL -> validador -> execução somente leitura
                    ^                              |
                    +---- erro volta para o LLM ---+   (até max_retries novas tentativas)
"""
from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass, field

from . import prompts
from .db import QueryError, QueryResult, run_query
from .llm import LLM, Message
from .validator import UnsafeSQLError, extract_sql, validate_sql


@dataclass
class AgentResult:
    question: str
    sql: str | None = None
    result: QueryResult | None = None
    answer: str | None = None
    error: str | None = None
    unanswerable: bool = False  # o LLM disse que os dados não respondem a pergunta
    attempts: int = 0
    latency_ms: float = 0.0
    history: list[str] = field(default_factory=list)  # SQL de cada tentativa, útil para depurar

    @property
    def ok(self) -> bool:
        return self.result is not None and self.error is None


class Text2SQLAgent:
    def __init__(
        self,
        llm: LLM,
        conn: sqlite3.Connection,
        schema: str,
        max_rows: int = 200,
        timeout_s: float = 10.0,
        max_retries: int = 1,
    ):
        self.llm = llm
        self.conn = conn
        self.schema = schema
        self.max_rows = max_rows
        self.timeout_s = timeout_s
        self.max_retries = max_retries

    def ask(self, question: str, explain: bool = False) -> AgentResult:
        start = time.perf_counter()
        out = AgentResult(question=question)
        messages: list[Message] = [
            {
                "role": "system",
                "content": prompts.SQL_SYSTEM_PROMPT.format(schema=self.schema, unanswerable=prompts.UNANSWERABLE),
            },
            {"role": "user", "content": question},
        ]

        for attempt in range(1, self.max_retries + 2):
            out.attempts = attempt
            raw = self.llm.complete(messages)

            if prompts.UNANSWERABLE in raw:
                out.unanswerable = True
                out.error = "a pergunta não pode ser respondida com estes dados"
                out.result = None
                break

            try:
                sql = validate_sql(extract_sql(raw))
                out.history.append(sql)
                out.sql = sql
                out.result = run_query(self.conn, sql, self.max_rows, self.timeout_s)
                out.error = None
                break
            except (UnsafeSQLError, QueryError) as exc:
                out.error = str(exc)
                out.result = None
                # devolve o erro para o LLM tentar corrigir (autocorreção)
                messages += [
                    {"role": "assistant", "content": raw},
                    {"role": "user", "content": prompts.RETRY_PROMPT.format(error=exc)},
                ]

        if explain and out.ok:
            out.answer = self._explain(question, out.sql or "", out.result)
        out.latency_ms = (time.perf_counter() - start) * 1000
        return out

    def _explain(self, question: str, sql: str, result: QueryResult, preview_rows: int = 20) -> str:
        header = " | ".join(result.columns)
        lines = [" | ".join(str(v) for v in row) for row in result.rows[:preview_rows]]
        truncated = result.truncated or len(result.rows) > preview_rows
        user = prompts.ANSWER_USER_PROMPT.format(
            question=question,
            sql=sql,
            n_rows=len(result.rows),
            truncated_note=", mostrando só as primeiras" if truncated else "",
            table="\n".join([header, *lines]),
        )
        return self.llm.complete(
            [{"role": "system", "content": prompts.ANSWER_SYSTEM_PROMPT}, {"role": "user", "content": user}]
        ).strip()
