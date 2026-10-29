"""Agente Text-to-SQL sobre o dataset público de e-commerce da Olist."""
from __future__ import annotations

from .agent import AgentResult, Text2SQLAgent
from .config import Settings, get_settings
from .db import connect_readonly
from .llm import OpenAICompatibleLLM
from .schema import describe_schema

__all__ = ["AgentResult", "Text2SQLAgent", "Settings", "get_settings", "build_agent"]


def build_agent(settings: Settings | None = None) -> Text2SQLAgent:
    """Monta o agente com o LLM e o banco configurados no .env."""
    settings = settings or get_settings()
    conn = connect_readonly(settings.db_path)
    return Text2SQLAgent(
        llm=OpenAICompatibleLLM(settings),
        conn=conn,
        schema=describe_schema(conn),
        max_rows=settings.max_rows,
        timeout_s=settings.query_timeout_s,
        max_retries=settings.max_retries,
    )
