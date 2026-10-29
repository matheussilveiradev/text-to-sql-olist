"""Compara o resultado do SQL gerado com o do SQL de referência (acerto por execução).

Em vez de comparar o texto do SQL (há muitas formas certas de escrever a mesma consulta),
executamos as duas e comparamos os resultados. A comparação tolera:
- colunas em outra ordem ou com outros nomes;
- colunas extras no resultado gerado;
- diferenças de arredondamento abaixo de 2 casas decimais.

Limitação conhecida: as colunas são comparadas uma a uma, então dois resultados com as mesmas
colunas, mas com valores trocados entre linhas, seriam considerados iguais. É raro nas perguntas
do conjunto, mas vale lembrar ao interpretar os números.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Sequence


def normalize(value):
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return round(float(value), 2)
    if isinstance(value, str):
        return value.strip()
    return value  # None


def results_match(
    gold_rows: Sequence[Sequence],
    pred_rows: Sequence[Sequence],
    order_matters: bool = False,
    compare_columns: Sequence[int] | None = None,
) -> bool:
    """True se cada coluna escolhida do resultado de referência aparece no resultado gerado."""
    if len(gold_rows) != len(pred_rows):
        return False
    if not gold_rows:
        return True

    gold_cols = [[normalize(v) for v in col] for col in zip(*gold_rows)]
    pred_cols = [[normalize(v) for v in col] for col in zip(*pred_rows)]

    def key(col):
        return col if order_matters else Counter(col)

    used: set[int] = set()
    for i in compare_columns if compare_columns is not None else range(len(gold_cols)):
        wanted = key(gold_cols[i])
        match = next((j for j, col in enumerate(pred_cols) if j not in used and key(col) == wanted), None)
        if match is None:
            return False
        used.add(match)
    return True
