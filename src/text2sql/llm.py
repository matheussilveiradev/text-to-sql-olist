"""Cliente de LLM compatível com a API da OpenAI.

Funciona com qualquer provedor que exponha esse formato (Google Gemini, Groq, NVIDIA,
OpenRouter, Ollama local, OpenAI): basta trocar LLM_BASE_URL, LLM_API_KEY e LLM_MODEL no .env.
"""
from __future__ import annotations

from typing import Protocol

from openai import OpenAI

from .config import Settings

Message = dict[str, str]


class LLM(Protocol):
    """Qualquer objeto com complete() serve. Nos testes, um LLM falso implementa isso."""

    def complete(self, messages: list[Message]) -> str: ...


class OpenAICompatibleLLM:
    def __init__(self, settings: Settings):
        if not settings.llm_model:
            raise ValueError("Defina LLM_MODEL no arquivo .env (veja .env.example).")
        # Ollama local não exige chave, mas o cliente precisa de algum valor
        self.client = OpenAI(api_key=settings.llm_api_key or "sem-chave", base_url=settings.llm_base_url)
        self.model = settings.llm_model

    def complete(self, messages: list[Message]) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0,  # respostas mais estáveis, o que importa para as avaliações
        )
        return response.choices[0].message.content or ""
