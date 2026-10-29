"""Base de teste pequena e sintética, com os mesmos arquivos e colunas do dataset real.

Assim os testes rodam sem baixar o dataset e sem chamar nenhum LLM.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "evals"))

from build_db import build  # noqa: E402

from text2sql.db import connect_readonly  # noqa: E402

CSVS = {
    "olist_customers_dataset.csv": """customer_id,customer_unique_id,customer_zip_code_prefix,customer_city,customer_state
c1,u1,01001,sao paulo,SP
c2,u2,20000,rio de janeiro,RJ
c3,u1,01001,sao paulo,SP
c4,u3,30100,belo horizonte,MG
""",
    "olist_orders_dataset.csv": """order_id,customer_id,order_status,order_purchase_timestamp,order_approved_at,order_delivered_carrier_date,order_delivered_customer_date,order_estimated_delivery_date
o1,c1,delivered,2017-01-05 10:00:00,2017-01-05 11:00:00,2017-01-06 09:00:00,2017-01-10 15:00:00,2017-01-20 00:00:00
o2,c2,delivered,2017-02-10 12:00:00,2017-02-10 13:00:00,2017-02-12 08:00:00,2017-03-01 10:00:00,2017-02-25 00:00:00
o3,c3,canceled,2017-02-15 08:00:00,2017-02-15 09:00:00,,,2017-03-01 00:00:00
o4,c4,delivered,2018-03-01 09:30:00,2018-03-01 10:00:00,2018-03-02 14:00:00,2018-03-08 18:00:00,2018-03-20 00:00:00
""",
    "olist_order_items_dataset.csv": """order_id,order_item_id,product_id,seller_id,shipping_limit_date,price,freight_value
o1,1,p1,s1,2017-01-09 10:00:00,100.00,10.50
o1,2,p2,s2,2017-01-09 10:00:00,49.90,8.00
o2,1,p1,s1,2017-02-14 12:00:00,100.00,12.00
o3,1,p3,s2,2017-02-19 08:00:00,300.00,20.00
o4,1,p2,s2,2018-03-05 09:30:00,59.90,9.90
""",
    "olist_order_payments_dataset.csv": """order_id,payment_sequential,payment_type,payment_installments,payment_value
o1,1,credit_card,3,168.40
o2,1,boleto,1,112.00
o3,1,credit_card,6,320.00
o4,1,voucher,1,30.00
o4,2,credit_card,2,39.80
""",
    "olist_order_reviews_dataset.csv": """review_id,order_id,review_score,review_comment_title,review_comment_message,review_creation_date,review_answer_timestamp
r1,o1,5,,Chegou antes do prazo,2017-01-11 00:00:00,2017-01-12 10:00:00
r2,o2,2,Atraso,Demorou demais,2017-03-02 00:00:00,2017-03-03 09:00:00
r4,o4,4,,,2018-03-09 00:00:00,2018-03-10 11:00:00
""",
    "olist_products_dataset.csv": """product_id,product_category_name,product_name_lenght,product_description_lenght,product_photos_qty,product_weight_g,product_length_cm,product_height_cm,product_width_cm
p1,beleza_saude,40,300,2,500,20,10,15
p2,cama_mesa_banho,35,250,1,1200,40,5,30
p3,moveis_decoracao,50,800,4,8000,100,50,60
""",
    "olist_sellers_dataset.csv": """seller_id,seller_zip_code_prefix,seller_city,seller_state
s1,13000,campinas,SP
s2,80000,curitiba,PR
""",
    "product_category_name_translation.csv": """product_category_name,product_category_name_english
beleza_saude,health_beauty
cama_mesa_banho,bed_bath_table
moveis_decoracao,furniture_decor
""",
}


@pytest.fixture(scope="session")
def db_path(tmp_path_factory) -> Path:
    raw = tmp_path_factory.mktemp("raw")
    for name, content in CSVS.items():
        # o arquivo de tradução real vem com BOM; reproduzimos isso para testar a leitura
        encoding = "utf-8-sig" if name.startswith("product_category") else "utf-8"
        (raw / name).write_text(content, encoding=encoding)
    path = raw.parent / "test.db"
    build(raw, path)
    return path


@pytest.fixture()
def conn(db_path):
    connection = connect_readonly(db_path)
    yield connection
    connection.close()


class FakeLLM:
    """LLM de mentira: devolve as respostas na ordem e guarda as mensagens recebidas."""

    def __init__(self, responses: list[str]):
        self.responses = list(responses)
        self.calls: list[list[dict]] = []

    def complete(self, messages):
        self.calls.append([dict(m) for m in messages])
        return self.responses.pop(0)


@pytest.fixture()
def fake_llm():
    return FakeLLM
