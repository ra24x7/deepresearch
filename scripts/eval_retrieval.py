"""Measure retrieval on the golden set: per channel, fused, and by question type.

Free with the identity reranker; only --reranker cohere_bedrock costs anything
(one rerank call per question).

    uv run python scripts/eval_retrieval.py --corpus evalv1 [--k 10] [--reranker identity|cohere_bedrock]
"""

import argparse
import sys
from pathlib import Path

import _bootstrap  # noqa: F401
from dotenv import load_dotenv

from clients import bedrock_runtime_client, embedding_provider, opensearch_client, postgres_session_factory
from config import RerankSettings, RetrievalSettings
from db.queries import chunks_by_paper as load_chunks_by_paper
from db.queries import claims_by_paper as load_claims_by_paper
from evals.report import fmt, mean, write_json_report
from evals.retrieval_eval import relevant_chunks_for_entry, relevant_claims_for_entry, score_question
from goldenset import load_answerable_entries
from retrieval.fusion import fuse
from retrieval.rerank.factory import build_reranker
from retrieval.router import route as route_query
from retrieval.schemas import CHANNEL_NAMES
from retrieval.search import candidate_pool_size, fusion_weights, run_channels

REPORT_PATH = Path("notebooks/phase3_retrieval/retrieval_eval.json")


def main(corpus: str, k: int, reranker_name: str) -> int:
    load_dotenv()
    settings = RetrievalSettings(top_k=k)
    provider = embedding_provider()
    search_client = opensearch_client()

    rerank_settings = RerankSettings(provider=reranker_name)
    rerank_client = None if reranker_name == "identity" else bedrock_runtime_client(rerank_settings.region)
    reranker = build_reranker(rerank_settings, rerank_client)

    answerable = load_answerable_entries()

    session_factory = postgres_session_factory()
    with session_factory() as session:
        chunks_by_paper = load_chunks_by_paper(session)
        claims_by_paper = load_claims_by_paper(session)

    size = candidate_pool_size(settings, k)
    records, unreachable, no_relevant = [], [], []

    for q in answerable:
        relevant = relevant_chunks_for_entry(q, chunks_by_paper)
        claim_relevant = relevant_claims_for_entry(q, claims_by_paper)
        # Claims are scored separately, not merged into the chunk relevance set:
        # retrieving the chunk already answers the question, so counting an
        # unfound claim as a miss would punish 25 questions to measure 4.
        if not relevant:
            no_relevant.append(q["id"])
            continue

        query = q["question"]
        # channels, weights and pool size come from the orchestrator: a local
        # copy would measure a system we do not ship
        hits_by_channel = run_channels(query, corpus, search_client, provider, size, settings)
        fused = fuse(hits_by_channel, weights=fusion_weights(settings), top_k=size)
        reranked = reranker.rerank(query, fused, k) if fused else []

        scored = score_question(hits_by_channel, reranked, relevant, k)
        if not scored.reachable:
            unreachable.append(q["id"])
        records.append(
            {
                "id": q["id"],
                "type": q["type"],
                "route": route_query(query),
                "relevant_chunks": len(relevant),
                "relevant_claims": len(claim_relevant),
                "claim_found": bool(claim_relevant & {h.doc_id for h in hits_by_channel["dense_claims"][:k]}),
                "reachable": scored.reachable,
                "fused_recall": scored.fused.recall,
                "fused_ndcg": scored.fused.ndcg,
                "per_channel": {n: {"recall": s.recall, "ndcg": s.ndcg} for n, s in scored.per_channel.items()},
            }
        )
        print(f"{q['id']:5} {q['type']:16} recall@{k}={fmt(scored.fused.recall)} "
              f"ndcg={fmt(scored.fused.ndcg)} reachable={scored.reachable}", flush=True)

    channels = CHANNEL_NAMES
    summary = {
        "questions_scored": len(records),
        "reranker": reranker.model_id,
        "k": k,
        "over_fetch": size,
        "reachable_rate": mean([1.0 if r["reachable"] else 0.0 for r in records]),
        "fused": {"recall": mean([r["fused_recall"] for r in records]), "ndcg": mean([r["fused_ndcg"] for r in records])},
        "per_channel": {
            c: {
                "recall": mean([r["per_channel"][c]["recall"] for r in records]),
                "ndcg": mean([r["per_channel"][c]["ndcg"] for r in records]),
            }
            for c in channels
        },
        "by_type": {
            t: {
                "n": len([r for r in records if r["type"] == t]),
                "recall": mean([r["fused_recall"] for r in records if r["type"] == t]),
            }
            for t in sorted({r["type"] for r in records})
        },
        "questions_with_a_relevant_claim": len([r for r in records if r["relevant_claims"]]),
        "claims_channel_found_it": len([r for r in records if r["claim_found"]]),
        "unreachable_questions": unreachable,
        "questions_without_relevant_chunk": no_relevant,
    }

    write_json_report(REPORT_PATH, {"summary": summary, "questions": records})

    print(f"\n=== {len(records)} questions, k={k}, over-fetch={size}, reranker={reranker.model_id}")
    print(f"{'channel':<14}{'recall@k':>10}{'ndcg@k':>10}")
    for c in channels:
        s = summary["per_channel"][c]
        if c == "dense_claims":
            # scores against chunk relevance by construction cannot apply: this
            # channel returns claim_hash ids. See the claims line below.
            print(f"{c:<14}{'n/a':>10}{'n/a':>10}")
            continue
        print(f"{c:<14}{fmt(s['recall']):>10}{fmt(s['ndcg']):>10}")
    print(f"{'FUSED':<14}{fmt(summary['fused']['recall']):>10}{fmt(summary['fused']['ndcg']):>10}")
    with_claim = summary["questions_with_a_relevant_claim"]
    print(f"claims channel: surfaced the relevant claim on {summary['claims_channel_found_it']} "
          f"of the {with_claim} questions that have one")
    print(f"\nreachable before rerank: {fmt(summary['reachable_rate'])}  (ceiling reranking cannot raise)")
    print("by type:", {t: f"{v['n']}q {fmt(v['recall'])}" for t, v in summary["by_type"].items()})
    if unreachable:
        print(f"unreachable: {', '.join(unreachable)}")
    if no_relevant:
        print(f"no relevant chunk found (excluded): {', '.join(no_relevant)}")
    print(f"report: {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="evalv1")
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--reranker", default="identity", choices=["identity", "cohere_bedrock"])
    args = ap.parse_args()
    sys.exit(main(args.corpus, args.k, args.reranker))
