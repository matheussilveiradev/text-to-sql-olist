import pytest

from text2sql.validator import UnsafeSQLError, extract_sql, validate_sql


def test_extracts_sql_from_markdown_fence():
    text = "Aqui está:\n```sql\nSELECT 1;\n```\nObrigado"
    assert extract_sql(text) == "SELECT 1;"


def test_uses_whole_text_when_there_is_no_fence():
    assert extract_sql("  SELECT 1  ") == "SELECT 1"


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT COUNT(*) FROM orders",
        "select * from orders;",
        "WITH t AS (SELECT 1 AS x) SELECT x FROM t",
        "SELECT * FROM reviews WHERE review_comment_message LIKE '%delete%'",
        "SELECT 'a;b' AS texto",
        "SELECT REPLACE(customer_city, ' ', '_') FROM customers",
        "-- comentário com drop\nSELECT 1",
    ],
)
def test_accepts_read_only_queries(sql):
    assert validate_sql(sql)  # não levanta exceção e devolve o SQL


def test_removes_trailing_semicolon():
    assert validate_sql("SELECT 1;") == "SELECT 1"


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM orders",
        "DROP TABLE orders",
        "UPDATE orders SET order_status = 'x'",
        "SELECT 1; DROP TABLE orders",
        "PRAGMA table_info(orders)",
        "ATTACH DATABASE 'outro.db' AS x",
        "WITH t AS (SELECT 1) INSERT INTO orders SELECT * FROM t",
        "",
        "   ",
    ],
)
def test_rejects_anything_that_is_not_a_single_select(sql):
    with pytest.raises(UnsafeSQLError):
        validate_sql(sql)
