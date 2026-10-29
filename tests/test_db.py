import sqlite3

import pytest

from text2sql.db import QueryError, connect_readonly, run_query
from text2sql.schema import describe_schema


def test_build_creates_all_tables(conn):
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert {"customers", "orders", "order_items", "payments", "reviews", "products", "sellers",
            "category_translation"} <= tables


def test_build_fixes_misspelled_columns_and_bom(conn):
    product_cols = [d[0] for d in conn.execute("SELECT * FROM products LIMIT 1").description]
    assert "product_name_length" in product_cols
    assert "product_name_lenght" not in product_cols
    translation_cols = [d[0] for d in conn.execute("SELECT * FROM category_translation LIMIT 1").description]
    assert translation_cols[0] == "product_category_name"  # sem o caractere BOM


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM orders",
        "UPDATE orders SET order_status = 'x'",
        "PRAGMA table_info(orders)",
        "ATTACH DATABASE ':memory:' AS outro",
        "CREATE TABLE x (a INT)",
    ],
)
def test_authorizer_blocks_writes_even_without_validator(conn, sql):
    with pytest.raises(QueryError):
        run_query(conn, sql)


def test_database_file_is_opened_read_only(db_path):
    conn = connect_readonly(db_path)
    conn.set_authorizer(None)  # mesmo sem o authorizer, o modo ro impede a escrita
    with pytest.raises(sqlite3.OperationalError):
        conn.execute("DELETE FROM orders")


def test_two_statements_are_rejected(conn):
    with pytest.raises(QueryError):
        run_query(conn, "SELECT 1; SELECT 2")


def test_row_limit_marks_result_as_truncated(conn):
    res = run_query(conn, "SELECT * FROM order_items", max_rows=2)
    assert len(res.rows) == 2
    assert res.truncated


def test_timeout_interrupts_long_queries(conn):
    endless = "WITH RECURSIVE n(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM n) SELECT COUNT(*) FROM n"
    with pytest.raises(QueryError, match="limite"):
        run_query(conn, endless, timeout_s=0.2)


def test_missing_database_has_clear_message(tmp_path):
    with pytest.raises(FileNotFoundError, match="build_db"):
        connect_readonly(tmp_path / "nao_existe.db")


def test_schema_description_has_tables_examples_and_notes(conn):
    text = describe_schema(conn)
    assert "CREATE TABLE" in text and '"orders"' in text
    assert "-- exemplos" in text
    assert "Notas sobre os dados" in text
