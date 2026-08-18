"""Answer the golden set end to end and grade it. Phase 4's measuring instrument.

Costs money on every question: one query embedding, one rerank call, one
generation, one judge call. Estimate before running with --dry-run.

    uv run python scripts/eval_answers.py --corpus evalv1 [--k 10]
        [--reranker identity|cohere_bedrock] [--limit N] [--dry-run]

Unlike scripts/eval_retrieval.py this scores **all** 150 questions, not the 136
answerable ones. The 8 `unanswerable` and 4 `out_of_domain` entries are the only
measurement of whether the system abstains instead of bluffing, which is the
behaviour Phase 4's guardrail exists to produce.
"""

import argparse
import json
import statistics
import sys
import time
from collections import defaultdict
from functools import partial
from pathlib import Path

import boto3
from botocore.config import Config
from dotenv import load_dotenv
from opensearchpy import OpenSearch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config import (
    BedrockSettings,
    EmbeddingSettings,
    GenerationSettings,
    JudgeSettings,
    RerankSettings,
    RetrievalSettings,
)
from evals.answer_eval import accumulate_cost, is_pass
from evals.judge import judge_answer, load_rubric
from generation.answer import generate_answer
from graph.pipeline import build_pipeline, initial_state
from ingestion.embeddings.factory import build_provider
from llm.bedrock import Usage, invoke, invoke_json
from llm.cost import CostLedger
from obs.tracing import build_tracer
from retrieval.rerank.factory import build_reranker
from retrieval.search import search

REPORT_PATH = Path("notebooks/phase4_orchestration/answer_eval.json")
GOLDEN_PATH = Path("data/golden_dataset.jsonl")
_TIMEOUT = 120

def mean(values: list[float]) -> float | None:
    return statistics.mean(values) if values else None


def fmt(value: float | None) -> str:
    return f"{value:.3f}" if value is not None else "  -  "


def main(corpus: str, k: int, reranker_name: str, limit: int | None, ids: str | None, dry_run: bool) -> int:
    questions = [json.loads(line) for line in GOLDEN_PATH.read_text().splitlines() if line.strip()]
    if ids:
        wanted = {i.strip() for i in ids.split(",") if i.strip()}
        questions = [q for q in questions if q["id"] in wanted]
    if limit:
        questions = questions[:limit]

    if dry_run:
        return _report_estimate(questions, reranker_name)

    load_dotenv()
    settings = RetrievalSettings(top_k=k)
    generation_settings = GenerationSettings()
    judge_settings = JudgeSettings()
    rerank_settings = RerankSettings(provider=reranker_name)

    bedrock = boto3.client(
        "bedrock-runtime", region_name=BedrockSettings().region, config=Config(read_timeout=_TIMEOUT)
    )
    provider = build_provider(EmbeddingSettings(), bedrock)
    search_client = OpenSearch(hosts=[{"host": "localhost", "port": 9200}], timeout=_TIMEOUT)
    rerank_client = (
        boto3.client("bedrock-runtime", region_name=rerank_settings.region, config=Config(read_timeout=_TIMEOUT))
        if reranker_name != "identity"
        else None
    )
    reranker = build_reranker(rerank_settings, rerank_client)
    tracer = build_tracer()
    rubric = load_rubric()

    # The graph takes plain callables; the counters live here so the graph stays
    # free of client and billing concerns.
    counters = {"embed_calls": 0, "rerank_documents": 0}

    def search_fn(question: str):
        result = search(question, corpus, search_client, provider, reranker, settings)
        counters["embed_calls"] += 1
        counters["rerank_documents"] += result.candidates_considered
        return result.hits

    def generate_fn(question: str, hits):
        return generate_answer(
            question, hits, partial(invoke, client=bedrock, settings=generation_settings), generation_settings
        )

    pipeline = build_pipeline(search_fn, generate_fn, generation_settings.model_id)
    judge_llm = partial(invoke_json, client=bedrock, settings=judge_settings)

    ledger = CostLedger()
    records, latencies = [], []

    errors: list[str] = []

    for i, q in enumerate(questions, 1):
        try:
            record, ledger = _score_one(
                q, pipeline, judge_llm, judge_settings, rubric, generation_settings,
                reranker_name, counters, ledger, tracer, latencies,
            )
        except Exception as exc:  # noqa: BLE001 — one bad response must not abort a paid batch
            errors.append(f"{q['id']}: {exc}")
            records.append(
                {"id": q["id"], "type": q["type"], "verdict": "ERROR", "reason": str(exc)[:300],
                 "passed": False, "error": True}
            )
            print(f"{q['id']:5} {q['type']:16} {'ERROR':10} FAIL   — {str(exc)[:80]}", flush=True)
            continue
        records.append(record)
        print(f"{q['id']:5} {q['type']:16} {record['verdict']:10} "
              f"{'PASS' if record['passed'] else 'FAIL'} {record['latency_s']:5.1f}s", flush=True)

    tracer.flush()
    summary = _summarise(records, latencies, ledger, k, reranker.model_id)
    summary["errors"] = errors

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps({"summary": summary, "questions": records}, indent=2) + "\n")
    _print_summary(summary, records)
    if errors:
        print(f"\n{len(errors)} question(s) errored:")
        for line in errors:
            print(f"  {line[:160]}")
    return 0


def _score_one(
    q, pipeline, judge_llm, judge_settings, rubric, generation_settings,
    reranker_name, counters, ledger, tracer, latencies,
):
    started = time.monotonic()
    state = pipeline.invoke(initial_state(q["question"]))
    elapsed = time.monotonic() - started
    latencies.append(elapsed)

    verdict = judge_answer(
        q["question"], state["answer"], q.get("reference_answer"), q.get("evidence", []), rubric,
        judge_llm, judge_settings,
    )

    # the graph's ledger holds this question's generation call and nothing else,
    # so its flat totals are exactly that call's usage
    generation_usage = Usage(
        input_tokens=state["ledger"].input_tokens, output_tokens=state["ledger"].output_tokens
    )
    ledger = accumulate_cost(
        ledger,
        generation_usage=generation_usage,
        generation_model=generation_settings.model_id,
        judge_usage=verdict.usage,
        judge_model=judge_settings.model_id,
        rerank_documents=counters["rerank_documents"] if reranker_name != "identity" else 0,
    )
    counters["rerank_documents"] = 0
    tracer.generation(
        name=f"answer:{q['id']}",
        model=generation_settings.model_id,
        prompt=q["question"],
        output=state["answer"] or "",
        usage=generation_usage,
        cost_usd=ledger.total_usd,
    )

    record = {
        "id": q["id"],
        "type": q["type"],
        "route": state["route"],
        "hits": len(state["hits"]),
        "abstained": state["abstained"],
        "verdict": verdict.verdict,
        "reason": verdict.reason,
        "passed": is_pass(q["type"], verdict.verdict, state["abstained"]),
        "latency_s": round(elapsed, 3),
        "answer": state["answer"],
    }
    return record, ledger


def _summarise(records: list[dict], latencies: list[float], ledger: CostLedger, k: int, reranker_model: str) -> dict:
    by_type: dict[str, list[bool]] = defaultdict(list)
    for r in records:
        by_type[r["type"]].append(r["passed"])

    ordered = sorted(latencies)
    return {
        "questions": len(records),
        "k": k,
        "reranker": reranker_model,
        "pass_rate": mean([1.0 if r["passed"] else 0.0 for r in records]),
        "by_type": {t: {"n": len(v), "pass_rate": mean([1.0 if p else 0.0 for p in v])} for t, v in sorted(by_type.items())},
        "verdicts": {v: len([r for r in records if r["verdict"] == v]) for v in ("CORRECT", "WRONG", "ABSTAINED", "ERROR")},
        "abstention_rate": mean([1.0 if r.get("abstained") else 0.0 for r in records]),
        "latency_s": {
            "p50": ordered[len(ordered) // 2] if ordered else None,
            "p95": ordered[int(len(ordered) * 0.95)] if ordered else None,
        },
        "cost": {
            "total_usd": ledger.total_usd,
            "per_query_usd": ledger.total_usd / len(records) if records else 0.0,
            "input_tokens": ledger.input_tokens,
            "output_tokens": ledger.output_tokens,
            "rerank_queries": ledger.rerank_queries,
            "embed_calls": ledger.embed_calls,
            # per-model split, so cost attribution does not need a second run
            "tokens_by_model": {
                m: {"input": t.input_tokens, "output": t.output_tokens}
                for m, t in ledger.tokens_by_model.items()
            },
            # non-empty means total_usd is a floor, not the bill (eval-log C1)
            "unpriced": list(ledger.unpriced),
        },
    }


def _print_summary(summary: dict, records: list[dict]) -> None:
    cost = summary["cost"]
    print(f"\n=== {summary['questions']} questions, k={summary['k']}, reranker={summary['reranker']}")
    print(f"pass rate: {fmt(summary['pass_rate'])}   verdicts: {summary['verdicts']}")
    print("by type:", {t: f"{v['n']}q {fmt(v['pass_rate'])}" for t, v in summary["by_type"].items()})
    print(f"latency: p50={fmt(summary['latency_s']['p50'])}s  p95={fmt(summary['latency_s']['p95'])}s")
    print(f"cost: ${cost['total_usd']:.4f} total, ${cost['per_query_usd']:.5f}/query")
    if cost["unpriced"]:
        print(f"  WARNING: cost is a FLOOR — unpriced components: {', '.join(cost['unpriced'])}")
    failures = [r["id"] for r in records if not r["passed"]]
    if failures:
        print(f"failed: {', '.join(failures)}")


def _report_estimate(questions: list[dict], reranker_name: str) -> int:
    n = len(questions)
    print(f"dry run — {n} questions would each make:")
    print("  1 query embedding   (cohere embed v4, UNPRICED — not published)")
    if reranker_name != "identity":
        print("  1 rerank call       (cohere rerank 3.5, $2.00 per 1,000 queries)")
    print("  1 generation call   (haiku 4.5, $1.00/$5.00 per 1M)")
    print("  1 judge call        (sonnet 4.6, $3.00/$15.00 per 1M)")
    rerank_usd = (n / 1_000 * 2.00) if reranker_name != "identity" else 0.0
    print(f"\nrerank floor: ${rerank_usd:.3f}")
    print("token costs depend on retrieved context length — run a --limit 5 sample first.")
    print("NOTE: token rates are Anthropic first-party, unverified against Bedrock (eval-log C1).")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", default="evalv1")
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--reranker", default="cohere_bedrock", choices=["identity", "cohere_bedrock"])
    parser.add_argument("--limit", type=int, default=None, help="score only the first N questions")
    parser.add_argument("--ids", default=None, help="comma-separated question ids, e.g. g001,g021")
    parser.add_argument("--dry-run", action="store_true", help="print the cost shape and exit")
    args = parser.parse_args()
    raise SystemExit(main(args.corpus, args.k, args.reranker, args.limit, args.ids, args.dry_run))
