"""Sweep fusion weights over cached retrieval results.

Retrieval is deterministic for a fixed query and index, so every channel runs
once and each weight configuration is scored by re-fusing the cached hits.
The sweep therefore costs one set of query embeddings, not one per config.

    uv run python scripts/sweep_fusion_weights.py [--k 10]
"""

import argparse
import sys
from collections import defaultdict
from pathlib import Path

import _bootstrap  # noqa: F401
from dotenv import load_dotenv

from clients import embedding_provider, opensearch_client, postgres_session_factory
from config import RetrievalSettings
from db.queries import chunks_by_paper as load_chunks_by_paper
from evals.report import fmt, mean, write_json_report
from evals.retrieval_eval import ndcg_at_k, recall_at_k, relevant_chunks_for_entry
from goldenset import load_answerable_entries
from retrieval.channels.entities import search_entities
from retrieval.fusion import fuse
from retrieval.schemas import CHANNEL_NAMES
from retrieval.search import candidate_pool_size, run_channels

REPORT_PATH = Path("notebooks/phase3_retrieval/fusion_weight_sweep.json")
CORPUS = "evalv1"
ENTITY_WEIGHTS = [0.0, 0.1, 0.25]
LINK_CEILINGS = [None, 30, 20, 10, 5]
SWEPT_CHANNEL = "entities"
FIXED_CHANNELS = [name for name in CHANNEL_NAMES if name != SWEPT_CHANNEL]


def main(k: int) -> int:
    load_dotenv()
    settings = RetrievalSettings(top_k=k)
    provider = embedding_provider()
    client = opensearch_client()

    answerable = load_answerable_entries()

    session_factory = postgres_session_factory()
    with session_factory() as session:
        chunks_by_paper = load_chunks_by_paper(session)

    size = candidate_pool_size(settings, k)
    cached = []
    for q in answerable:
        relevant = relevant_chunks_for_entry(q, chunks_by_paper)
        if not relevant:
            continue
        query = q["question"]
        # The orchestrator's fan-out gives the fixed channels; the entity channel
        # is run once per link ceiling, which is what the sweep varies.
        cached.append(
            (
                q,
                relevant,
                {
                    **run_channels(query, CORPUS, client, provider, size, settings, FIXED_CHANNELS),
                    **{
                        f"{SWEPT_CHANNEL}@{ceiling}": search_entities(
                            client, CORPUS, query, size, settings.entity_damping, ceiling
                        )
                        for ceiling in LINK_CEILINGS
                    },
                },
            )
        )
        print(f"retrieved {q['id']}", flush=True)

    print(f"\n{len(cached)} questions cached; sweeping without further embedding\n")
    print(f"{'link ceiling':>13}{'weight':>8}{'recall@k':>10}{'ndcg@k':>10}")
    rows = []
    for ceiling in LINK_CEILINGS:
      for weight in ENTITY_WEIGHTS:
        weights = {"bm25": 1.0, "dense_chunks": 1.0, "dense_claims": 1.0, "entities": weight}
        recalls, ndcgs, by_type = [], [], defaultdict(list)
        for q, relevant, hits in cached:
            selected = {n: h for n, h in hits.items() if n in FIXED_CHANNELS}
            selected[SWEPT_CHANNEL] = hits[f"{SWEPT_CHANNEL}@{ceiling}"]
            fused = fuse(selected, weights=weights, top_k=k)
            ranked = [h.doc_id for h in fused]
            r = recall_at_k(ranked, relevant, k)
            recalls.append(r)
            ndcgs.append(ndcg_at_k(ranked, relevant, k))
            by_type[q["type"]].append(r)
        row = {
            "link_ceiling": ceiling,
            "entity_weight": weight,
            "recall": mean(recalls),
            "ndcg": mean(ndcgs),
            "by_type": {t: mean(v) for t, v in by_type.items()},
        }
        rows.append(row)
        print(f"{ceiling!s:>13}{weight:>8}{fmt(row['recall']):>10}{fmt(row['ndcg']):>10}")

    write_json_report(REPORT_PATH, {"k": k, "questions": len(cached), "results": rows})
    print(f"\nreport: {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=10)
    args = ap.parse_args()
    sys.exit(main(args.k))
