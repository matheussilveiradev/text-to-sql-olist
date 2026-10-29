"""Configuração lida do arquivo .env (veja .env.example)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    llm_base_url: str | None
    llm_api_key: str | None
    llm_model: str | None
    db_path: Path
    max_rows: int
    query_timeout_s: float
    max_retries: int


def get_settings() -> Settings:
    return Settings(
        llm_base_url=os.getenv("LLM_BASE_URL") or None,
        llm_api_key=os.getenv("LLM_API_KEY") or None,
        llm_model=os.getenv("LLM_MODEL") or None,
        db_path=Path(os.getenv("DB_PATH") or ROOT / "data" / "olist.db"),
        max_rows=int(os.getenv("MAX_ROWS", "200")),
        query_timeout_s=float(os.getenv("QUERY_TIMEOUT_S", "10")),
        max_retries=int(os.getenv("MAX_RETRIES", "1")),
    )
