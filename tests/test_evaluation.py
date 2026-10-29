import pytest

from run_evals import gold_sqls, load_questions
from text2sql.db import run_query
from text2sql.evaluation import results_match
from text2sql.validator import validate_sql

GOLD = [("SP", 10.0), ("RJ", 5.0)]


def test_same_result_matches():
    assert results_match(GOLD, [("SP", 10.0), ("RJ", 5.0)])


def test_column_order_and_names_do_not_matter():
    assert results_match(GOLD, [(10, "SP"), (5, "RJ")])


def test_extra_columns_are_allowed():
    assert results_match(GOLD, [("SP", 10.0, 3), ("RJ", 5.0, 1)])


def test_rounding_below_two_decimals_is_ignored():
    assert results_match([(1.23,)], [(1.2299999,)])


def test_different_values_do_not_match():
    assert not results_match(GOLD, [("SP", 10.0), ("RJ", 6.0)])


def test_row_count_must_match():
    assert not results_match(GOLD, [("SP", 10.0)])


def test_order_is_checked_only_when_it_matters():
    reversed_rows = [("RJ", 5.0), ("SP", 10.0)]
    assert results_match(GOLD, reversed_rows, order_matters=False)
    assert not results_match(GOLD, reversed_rows, order_matters=True)


def test_compare_only_selected_columns():
    # rótulos diferentes ("sim"/"não" em vez de "SP"/"RJ"), mas os números batem
    assert results_match(GOLD, [("sim", 10.0), ("não", 5.0)], compare_columns=[1])


@pytest.mark.parametrize("item", load_questions(), ids=lambda q: q["id"])
def test_reference_sql_runs_on_the_schema(conn, item):
    """Garante que todo SQL de referência usa tabelas e colunas que existem."""
    if item.get("unanswerable"):
        assert not gold_sqls(item)
        return
    for sql in gold_sqls(item):
        run_query(conn, validate_sql(sql))
