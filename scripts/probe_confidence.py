"""Measure the rerank confidence distribution, so the escape-hatch threshold is
calibrated rather than guessed.

Retrieval only -- no generation, no judge. For each golden question it records
the reranker's relevance score for its own top hit, then joins that against the
pass/fail column of an existing answer-eval report. The join is valid only while
retrieval is unchanged between the two runs: `search.py` fans out to every
channel regardless of route, so the router change of 2026-08-25 moved no hits.

Cost: one query embedding + one rerank call per question. At 150 questions that
is $0.30 of rerank plus 150 unpriced embeddings.

    uv run python scripts/probe_confidence.py --corpus evalv1 [--k 10] [--dry-run]
"""

import argparse
import json
import sys
from pathlib import Path

import boto3
from botocore.config import Config
from dotenv import load_dotenv
from opensearchpy import OpenSearch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config import BedrockSettings, EmbeddingSettings, PostgresSettings, RerankSettings, RetrievalSettings
from db.session import get_engine
from ingestion.embeddings.factory import build_provider
from retrieval.rerank.factory import build_reranker
from retrieval.search import search
from retrieval.vocabulary import load_entity_vocabulary

REPORT_PATH = Path("notebooks/phase4_orchestration/confidence_probe.json")
ANSWER_EVAL_PATH = Path("notebooks/phase4_orchestration/answer_eval.json")
GOLDEN_PATH = Path("data/golden_dataset.jsonl")
CANDIDATE_THRESHOLDS = (0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50)
_TIMEOUT = 120
_EXIT_CRITERION_MAX_FIRE_RATE = 0.30


def main(corpus: str, k: int, dry_run: bool) -> int:
    questions = [json.loads(line) for line in GOLDEN_PATH.read_text().splitlines() if line.strip()]
    if dry_run:
        print(f"dry run — {len(questions)} questions, each 1 embedding + 1 rerank call")
        print(f"rerank floor: ${len(questions) / 1_000 * 2.00:.3f}; embeddings unpriced (eval-log C1)")
        return 0

    load_dotenv()
    settings = RetrievalSettings(top_k=k)
    rerank_settings = RerankSettings(provider="cohere_bedrock")
    bedrock = boto3.client(
        "bedrock-runtime", region_name=BedrockSettings().region, config=Config(read_timeout=_TIMEOUT)
    )
    provider = build_provider(EmbeddingSettings(), bedrock)
    search_client = OpenSearch(hosts=[{"host": "localhost", "port": 9200}], timeout=_TIMEOUT)
    reranker = build_reranker(
        rerank_settings,
        boto3.client("bedrock-runtime", region_name=rerank_settings.region, config=Config(read_timeout=_TIMEOUT)),
    )
    vocabulary = load_entity_vocabulary(get_engine(PostgresSettings()))
    passed_by_id = _load_pass_column()

    records = []
    for q in questions:
        result = search(q["question"], corpus, search_client, provider, reranker, settings, vocabulary)
        confidence = result.hits[0].score if result.hits else 0.0
        records.append(
            {
                "id": q["id"],
                "type": q["type"],
                "route": result.route,
                "hits": len(result.hits),
                "confidence": confidence,
                "answer_passed": passed_by_id.get(q["id"]),
            }
        )
        print(f"{q['id']:5} {q['type']:16} confidence={confidence:.4f} hits={len(result.hits)}", flush=True)

    report = {"k": k, "reranker": reranker.model_id, "thresholds": _analyse(records), "questions": records}
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n")
    _print_analysis(report["thresholds"], records)
    return 0


def _load_pass_column() -> dict[str, bool]:
    if not ANSWER_EVAL_PATH.exists():
        return {}
    report = json.loads(ANSWER_EVAL_PATH.read_text())
    return {r["id"]: r["passed"] for r in report["questions"]}


def _analyse(records: list[dict]) -> list[dict]:
    """For each candidate threshold: how often the hatch fires, and whether it
    fires on the questions that actually needed it."""
    judged = [r for r in records if r["answer_passed"] is not None]
    failures = sum(1 for r in judged if not r["answer_passed"])
    rows = []
    for threshold in CANDIDATE_THRESHOLDS:
        fired = [r for r in records if r["confidence"] < threshold]
        fired_judged = [r for r in judged if r["confidence"] < threshold]
        caught = sum(1 for r in fired_judged if not r["answer_passed"])
        rows.append(
            {
                "threshold": threshold,
                "fire_rate": len(fired) / len(records) if records else 0.0,
                "meets_exit_criterion": len(fired) / len(records) < _EXIT_CRITERION_MAX_FIRE_RATE if records else False,
                # of the queries it fires on, how many were answered wrongly
                "precision": caught / len(fired_judged) if fired_judged else None,
                # of the wrong answers, how many it would have had a chance to repair
                "recall_of_failures": caught / failures if failures else None,
            }
        )
    return rows


def _print_analysis(rows: list[dict], records: list[dict]) -> None:
    scored = sorted(r["confidence"] for r in records)
    print(f"\n=== {len(records)} questions, confidence deciles")
    print("  " + "  ".join(f"p{p}={scored[min(int(len(scored) * p / 100), len(scored) - 1)]:.3f}" for p in (5, 10, 25, 50, 75, 90)))
    print(f"\n{'threshold':>10} {'fires':>7} {'<30%?':>6} {'precision':>10} {'catches':>8}")
    for row in rows:
        precision = f"{row['precision']:.3f}" if row["precision"] is not None else "  -  "
        catches = f"{row['recall_of_failures']:.3f}" if row["recall_of_failures"] is not None else "  -  "
        print(f"{row['threshold']:>10.2f} {row['fire_rate']:>7.3f} {'yes' if row['meets_exit_criterion'] else 'NO':>6} {precision:>10} {catches:>8}")
    print("\nprecision = share of fired queries the last answer eval got wrong")
    print("catches   = share of wrong answers the hatch would get a chance to repair")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", default="evalv1")
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--dry-run", action="store_true", help="print the cost shape and exit")
    args = parser.parse_args()
    raise SystemExit(main(args.corpus, args.k, args.dry_run))
