"""Converte os CSVs do dataset Olist em um banco SQLite com índices.

Uso:
    python scripts/build_db.py                      # lê data/raw, grava data/olist.db
    python scripts/build_db.py --raw outra/pasta --db outro.db
    python scripts/build_db.py --with-geolocation   # inclui a tabela geolocation (~1 milhão de linhas)
"""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

# arquivo CSV -> nome da tabela no SQLite (nomes curtos ajudam o LLM)
TABLES = {
    "olist_customers_dataset.csv": "customers",
    "olist_orders_dataset.csv": "orders",
    "olist_order_items_dataset.csv": "order_items",
    "olist_order_payments_dataset.csv": "payments",
    "olist_order_reviews_dataset.csv": "reviews",
    "olist_products_dataset.csv": "products",
    "olist_sellers_dataset.csv": "sellers",
    "product_category_name_translation.csv": "category_translation",
}
GEOLOCATION = {"olist_geolocation_dataset.csv": "geolocation"}

# o dataset original tem "lenght" escrito errado; corrigir evita que o LLM erre o nome da coluna
RENAME_COLUMNS = {
    "product_name_lenght": "product_name_length",
    "product_description_lenght": "product_description_length",
}

INDEXES = [
    ("orders", "customer_id"),
    ("orders", "order_purchase_timestamp"),
    ("order_items", "order_id"),
    ("order_items", "product_id"),
    ("order_items", "seller_id"),
    ("payments", "order_id"),
    ("reviews", "order_id"),
]
PRIMARY_KEYS = {
    "customers": "customer_id",
    "orders": "order_id",
    "products": "product_id",
    "sellers": "seller_id",
    "category_translation": "product_category_name",
}


def build(raw_dir: Path, db_path: Path, with_geolocation: bool = False) -> dict[str, int]:
    """Cria o banco do zero e devolve a contagem de linhas por tabela."""
    files = dict(TABLES)
    if with_geolocation:
        files.update(GEOLOCATION)

    missing = [name for name in files if not (raw_dir / name).exists()]
    if missing:
        raise FileNotFoundError(
            f"Arquivos não encontrados em {raw_dir}: {', '.join(missing)}. "
            "Rode scripts/download_data.py ou baixe o dataset manualmente (veja o README)."
        )

    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    counts: dict[str, int] = {}
    with sqlite3.connect(db_path) as conn:
        for csv_name, table in files.items():
            # utf-8-sig remove o BOM que aparece no cabeçalho de alguns CSVs
            df = pd.read_csv(raw_dir / csv_name, encoding="utf-8-sig")
            df = df.rename(columns=RENAME_COLUMNS)
            df.to_sql(table, conn, index=False)
            counts[table] = len(df)

        for table, column in PRIMARY_KEYS.items():
            if table in counts:
                conn.execute(f"CREATE UNIQUE INDEX idx_{table}_pk ON {table}({column})")
        for table, column in INDEXES:
            if table in counts:
                conn.execute(f"CREATE INDEX idx_{table}_{column} ON {table}({column})")
        conn.execute("ANALYZE")

    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--raw", type=Path, default=ROOT / "data" / "raw")
    parser.add_argument("--db", type=Path, default=ROOT / "data" / "olist.db")
    parser.add_argument("--with-geolocation", action="store_true")
    args = parser.parse_args()

    counts = build(args.raw, args.db, args.with_geolocation)
    for table, n in counts.items():
        print(f"{table:<22} {n:>9,} linhas".replace(",", "."))
    print(f"\nBanco criado em {args.db}")


if __name__ == "__main__":
    main()
