"""Mede a qualidade do agente no conjunto de perguntas de evals/questions.jsonl.

Métricas:
- acerto por execução: o resultado do SQL gerado bate com o do SQL de referência;
- recusas corretas: perguntas que os dados não respondem devem ser recusadas;
- latência (média e p95) e número médio de tentativas.

Uso:
    python evals/run_evals.py                  # roda tudo com o modelo do .env
    python evals/run_evals.py --limit 5        # só as 5 primeiras perguntas
    python evals/run_evals.py --ids q05 q17    # perguntas específicas
    python evals/run_evals.py --check-gold     # só confere se o SQL de referência roda (não usa LLM)
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from text2sql import build_agent, get_settings  # noqa: E402
from text2sql.db import QueryError, connect_readonly, run_query  # noqa: E402
from text2sql.evaluation import results_match  # noqa: E402

QUESTIONS_PATH = ROOT / "evals" / "questions.jsonl"
RESULTS_DIR = ROOT / "evals" / "results"
GOLD_MAX_ROWS = 10_000


def load_questions(path: Path = QUESTIONS_PATH) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def gold_sqls(item: dict) -> list[str]:
    gold = item.get("gold_sql") or []
    return [gold] if isinstance(gold, str) else list(gold)


def check_gold(conn, questions: list[dict]) -> int:
    """Executa cada SQL de referência e mostra o começo do resultado. Devolve o número de falhas."""
    failures = 0
    for item in questions:
        for sql in gold_sqls(item):
            try:
                res = run_query(conn, sql, max_rows=GOLD_MAX_ROWS, timeout_s=60)
                preview = res.rows[:3]
                print(f"ok    {item['id']}  {len(res.rows):>5} linhas  {preview}")
            except QueryError as exc:
                failures += 1
                print(f"ERRO  {item['id']}  {exc}\n      {sql}")
    return failures


def evaluate(agent, conn, questions: list[dict]) -> list[dict]:
    records = []
    for item in questions:
        res = agent.ask(item["question"])
        record = {
            "id": item["id"],
            "question": item["question"],
            "tags": item.get("tags", []),
            "sql": res.sql,
            "attempts": res.attempts,
            "latency_ms": round(res.latency_ms),
            "error": res.error,
        }

        if item.get("unanswerable"):
            record["correct"] = res.unanswerable
            record["reason"] = "recusou" if res.unanswerable else "deveria ter recusado"
        elif not res.ok:
            record["correct"] = False
            record["reason"] = "recusou sem motivo" if res.unanswerable else "erro no SQL"
        else:
            # o resultado do agente vem limitado a max_rows; reexecutamos para comparar tudo
            pred = run_query(conn, res.sql, max_rows=GOLD_MAX_ROWS, timeout_s=60)
            golds = [run_query(conn, sql, max_rows=GOLD_MAX_ROWS, timeout_s=60) for sql in gold_sqls(item)]
            record["correct"] = any(
                results_match(g.rows, pred.rows, item.get("order_matters", False), item.get("compare_columns"))
                for g in golds
            )
            record["reason"] = "ok" if record["correct"] else "resultado diferente"

        mark = "✓" if record["correct"] else "✗"
        print(f"{mark} {item['id']}  {record['reason']:<22} {record['latency_ms'] / 1000:5.1f}s  {item['question']}")
        records.append(record)
    return records


def summarize(records: list[dict]) -> dict:
    latencies = [r["latency_ms"] for r in records]
    p95_index = max(0, round(0.95 * len(latencies)) - 1)
    return {
        "total": len(records),
        "corretas": sum(r["correct"] for r in records),
        "acerto": round(sum(r["correct"] for r in records) / len(records), 3),
        "latencia_media_ms": round(statistics.mean(latencies)),
        "latencia_p95_ms": sorted(latencies)[p95_index],
        "tentativas_media": round(statistics.mean(r["attempts"] for r in records), 2),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--ids", nargs="+")
    parser.add_argument("--check-gold", action="store_true")
    args = parser.parse_args()

    settings = get_settings()
    questions = load_questions()
    if args.ids:
        questions = [q for q in questions if q["id"] in set(args.ids)]
    if args.limit:
        questions = questions[: args.limit]

    conn = connect_readonly(settings.db_path)
    if args.check_gold:
        sys.exit(1 if check_gold(conn, questions) else 0)

    if not questions:
        sys.exit("Nenhuma pergunta selecionada.")
    agent = build_agent(settings)
    records = evaluate(agent, conn, questions)
    summary = summarize(records)

    print(
        f"\nAcerto: {summary['corretas']}/{summary['total']} ({summary['acerto']:.0%}) | "
        f"latência média {summary['latencia_media_ms'] / 1000:.1f}s, p95 {summary['latencia_p95_ms'] / 1000:.1f}s | "
        f"tentativas média {summary['tentativas_media']}"
    )

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    model = (settings.llm_model or "modelo").replace("/", "_").replace(":", "_")
    out_path = RESULTS_DIR / f"{time.strftime('%Y%m%d-%H%M%S')}_{model}.json"
    payload = {"model": settings.llm_model, "settings": {**asdict(settings), "llm_api_key": None, "db_path": str(settings.db_path)},
               "summary": summary, "records": records}
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Detalhes salvos em {out_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
