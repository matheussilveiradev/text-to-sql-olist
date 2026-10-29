"""Baixa o dataset público da Olist do Kaggle e copia os CSVs para data/raw.

Dataset: https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce (licença CC BY-NC-SA 4.0)

Se o download falhar (por exemplo, pedindo login), baixe o .zip pela página acima,
extraia e coloque os CSVs em data/raw.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import kagglehub

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"


def main() -> None:
    source = Path(kagglehub.dataset_download("olistbr/brazilian-ecommerce"))
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    copied = 0
    for csv in source.rglob("*.csv"):
        shutil.copy2(csv, RAW_DIR / csv.name)
        copied += 1
    print(f"{copied} arquivos CSV copiados para {RAW_DIR}")


if __name__ == "__main__":
    main()
