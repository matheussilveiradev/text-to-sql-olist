from text2sql.agent import Text2SQLAgent
from text2sql.prompts import UNANSWERABLE


def make_agent(llm, conn, **kwargs):
    return Text2SQLAgent(llm=llm, conn=conn, schema="(esquema de teste)", **kwargs)


def test_answers_on_first_try(conn, fake_llm):
    llm = fake_llm(["```sql\nSELECT COUNT(*) AS pedidos FROM orders\n```"])
    res = make_agent(llm, conn).ask("Quantos pedidos existem?")
    assert res.ok
    assert res.result.rows == [(4,)]
    assert res.attempts == 1
    assert "(esquema de teste)" in llm.calls[0][0]["content"]


def test_sends_error_back_and_recovers(conn, fake_llm):
    llm = fake_llm([
        "```sql\nSELECT coluna_que_nao_existe FROM orders\n```",
        "```sql\nSELECT COUNT(*) FROM orders\n```",
    ])
    res = make_agent(llm, conn, max_retries=1).ask("Quantos pedidos existem?")
    assert res.ok
    assert res.attempts == 2
    assert len(res.history) == 2
    retry_message = llm.calls[1][-1]["content"]
    assert "coluna_que_nao_existe" in retry_message  # o erro do SQLite volta para o LLM


def test_gives_up_after_max_retries(conn, fake_llm):
    llm = fake_llm(["DELETE FROM orders", "DROP TABLE orders"])
    res = make_agent(llm, conn, max_retries=1).ask("Apague tudo")
    assert not res.ok
    assert res.attempts == 2
    assert res.error


def test_recognizes_unanswerable_question(conn, fake_llm):
    llm = fake_llm([UNANSWERABLE])
    res = make_agent(llm, conn).ask("Qual a idade média dos clientes?")
    assert res.unanswerable
    assert not res.ok
    assert res.attempts == 1


def test_explain_uses_a_second_llm_call(conn, fake_llm):
    llm = fake_llm([
        "```sql\nSELECT order_status, COUNT(*) AS pedidos FROM orders GROUP BY order_status\n```",
        "Há 3 pedidos entregues e 1 cancelado.",
    ])
    res = make_agent(llm, conn).ask("Quantos pedidos por status?", explain=True)
    assert res.answer == "Há 3 pedidos entregues e 1 cancelado."
    assert "delivered" in llm.calls[1][1]["content"]  # o resultado vai no prompt da explicação
