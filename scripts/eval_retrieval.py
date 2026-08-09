"""Measure retrieval on the golden set: per channel, fused, and by question type.

Free with the identity reranker; only --reranker cohere_bedrock costs anything
(one rerank call per question).

    uv run python scripts/eval_retrieval.py --corpus evalv1 [--k 10] [--reranker identity|cohere_bedrock]
"""

import argparse
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

import boto3
from botocore.config import Config
from dotenv import load_dotenv
from opensearchpy import OpenSearch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config import BedrockSettings, EmbeddingSettings, PostgresSettings, RerankSettings, RetrievalSettings
from db.models import Chunk, Claim
from db.session import get_engine, get_session_factory
from evals.retrieval_eval import relevant_chunk_ids, relevant_claim_hashes, score_question
from ingestion.embeddings.factory import build_provider
from retrieval.channels.bm25 import search_bm25
from retrieval.channels.dense import search_dense_chunks, search_dense_claims
from retrieval.channels.entities import search_entities
from retrieval.fusion import fuse
from retrieval.rerank.factory import build_reranker
from retrieval.router import route as route_query

REPORT_PATH = Path("notebooks/phase3_retrieval/retrieval_eval.json")
_TIMEOUT = 120


def mean(values: list[float | None]) -> float | None:
    present = [v for v in values if v is not None]
    return statistics.mean(present) if present else None


def fmt(value: float | None) -> str:
    return f"{value:.3f}" if value is not None else "  -  "


def main(corpus: str, k: int, reranker_name: str) -> int:
    load_dotenv()
    settings = RetrievalSettings(top_k=k)
    bedrock = boto3.client(
        "bedrock-runtime", region_name=BedrockSettings().region, config=Config(read_timeout=_TIMEOUT)
    )
    provider = build_provider(EmbeddingSettings(), bedrock)
    search_client = OpenSearch(hosts=[{"host": "localhost", "port": 9200}], timeout=_TIMEOUT)

    rerank_settings = RerankSettings(provider=reranker_name)
    rerank_client = (
        boto3.client("bedrock-runtime", region_name=rerank_settings.region, config=Config(read_timeout=_TIMEOUT))
        if reranker_name != "identity"
        else None
    )
    reranker = build_reranker(rerank_settings, rerank_client)

    questions = [json.loads(line) for line in Path("data/golden_dataset.jsonl").read_text().splitlines() if line.strip()]
    answerable = [q for q in questions if q.get("expected_behavior") == "answer"]

    session_factory = get_session_factory(get_engine(PostgresSettings()))
    with session_factory() as session:
        chunks_by_paper: dict[str, list[tuple[str, str]]] = defaultdict(list)
        for chunk in session.query(Chunk).all():
            chunks_by_paper[chunk.arxiv_id].append((chunk.chunk_id, chunk.text))
        claims_by_paper: dict[str, list[tuple[str, str]]] = defaultdict(list)
        for claim in session.query(Claim).all():
            claims_by_paper[claim.arxiv_id].append((claim.claim_hash, claim.claim_text))

    size = max(settings.over_fetch_multiplier * k, settings.min_candidates)
    records, unreachable, no_evidence, unmatched = [], [], [], []

    for q in answerable:
        relevant: set[str] = set()
        claim_relevant: set[str] = set()
        for ev in q["evidence"]:
            if ev.get("quote"):
                relevant |= relevant_chunk_ids(ev["quote"], chunks_by_paper.get(ev["arxiv_id"], []))
                claim_relevant |= relevant_claim_hashes(
                    ev["quote"], q.get("reference_answer", ""), claims_by_paper.get(ev["arxiv_id"], [])
                )
        # Claims are scored separately, not merged into the chunk relevance set:
        # retrieving the chunk already answers the question, so counting an
        # unfound claim as a miss would punish 25 questions to measure 4.
        if not relevant:
            # No quotes at all is by design (g038: metadata-computed answer);
            # quotes that match nothing mean the golden set and index drifted.
            has_quotes = any(ev.get("quote") for ev in q["evidence"])
            (unmatched if has_quotes else no_evidence).append(q["id"])
            continue

        query = q["question"]
        hits_by_channel = {
            "bm25": search_bm25(search_client, corpus, query, size),
            "dense_chunks": search_dense_chunks(search_client, corpus, provider, query, size),
            "dense_claims": search_dense_claims(search_client, corpus, provider, query, size),
            "entities": search_entities(search_client, corpus, query, size, settings.entity_damping),
        }
        # must mirror the orchestrator, or the eval measures a system we do not ship
        weights = {"bm25": 1.0, "dense_chunks": 1.0, "dense_claims": 1.0, "entities": settings.entity_weight}
        fused = fuse(hits_by_channel, weights=weights, top_k=size)
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

    channels = ["bm25", "dense_chunks", "dense_claims", "entities"]
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
        "excluded_no_evidence": no_evidence,
        "evidence_unmatched": unmatched,
    }

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps({"summary": summary, "questions": records}, indent=2) + "\n")

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
    if no_evidence:
        print(f"excluded, no evidence by design: {', '.join(no_evidence)}")
    if unmatched:
        print(f"WARNING — evidence quotes matched no chunk, golden set and index have drifted: {', '.join(unmatched)}")
    print(f"report: {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="evalv1")
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--reranker", default="identity", choices=["identity", "cohere_bedrock"])
    args = ap.parse_args()
    sys.exit(main(args.corpus, args.k, args.reranker))
