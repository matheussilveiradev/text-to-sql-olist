"""Interface web do agente. Rode com: streamlit run app.py"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from text2sql import build_agent  # noqa: E402

EXAMPLES = [
    "Quais as 5 categorias com maior faturamento?",
    "Como evoluiu o número de pedidos por mês em 2017?",
    "Qual o tempo médio de entrega por estado do cliente?",
    "A nota da avaliação cai quando a entrega atrasa?",
]

st.set_page_config(page_title="Pergunte aos dados · Olist", layout="wide")


@st.cache_resource
def get_agent():
    return build_agent()


def set_question(text: str) -> None:
    st.session_state["question"] = text


def show_chart(df: pd.DataFrame) -> None:
    """Desenha um gráfico simples quando o resultado tem formato de categoria + número."""
    if df.shape[1] != 2 or len(df) < 2 or not pd.api.types.is_numeric_dtype(df.iloc[:, 1]):
        return
    data = df.set_index(df.columns[0])
    looks_like_time = df.iloc[:, 0].astype(str).str.match(r"^\d{4}(-\d{2})?").all()
    if looks_like_time:
        st.line_chart(data)
    else:
        st.bar_chart(data)


st.title("Pergunte aos dados")
st.caption("Agente que transforma perguntas em português em SQL sobre o dataset público de e-commerce da Olist.")

try:
    agent = get_agent()
except Exception as exc:  # banco ausente, .env incompleto etc.
    st.error(f"Não consegui iniciar o agente: {exc}")
    st.stop()

columns = st.columns(len(EXAMPLES))
for col, example in zip(columns, EXAMPLES):
    col.button(example, on_click=set_question, args=(example,), width="stretch")

question = st.text_input("Sua pergunta", key="question", placeholder="Ex.: qual estado tem o maior ticket médio?")

if st.button("Perguntar", type="primary") and question:
    with st.spinner("Gerando e executando o SQL..."):
        result = agent.ask(question, explain=True)

    if not result.ok:
        st.warning(f"Não consegui responder: {result.error}")
        if result.sql:
            st.code(result.sql, language="sql")
        st.stop()

    st.markdown(result.answer or "")
    df = pd.DataFrame(result.result.rows, columns=result.result.columns)
    show_chart(df)
    st.dataframe(df, width="stretch", hide_index=True)
    if result.result.truncated:
        st.caption(f"Mostrando só as primeiras {len(df)} linhas.")

    with st.expander("Ver o SQL gerado"):
        st.code(result.sql, language="sql")
    st.caption(f"{result.attempts} tentativa(s) · {result.latency_ms / 1000:.1f} s")
