"""Sweep fusion weights over cached retrieval results.

Retrieval is deterministic for a fixed query and index, so every channel runs
once and each weight configuration is scored by re-fusing the cached hits.
The sweep therefore costs one set of query embeddings, not one per config.

    uv run python scripts/sweep_fusion_weights.py [--k 10]
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

from config import BedrockSettings, EmbeddingSettings, PostgresSettings, RetrievalSettings
from db.models import Chunk
from db.session import get_engine, get_session_factory
from evals.retrieval_eval import ndcg_at_k, recall_at_k, relevant_chunk_ids
from ingestion.embeddings.factory import build_provider
from retrieval.channels.bm25 import search_bm25
from retrieval.channels.dense import search_dense_chunks, search_dense_claims
from retrieval.channels.entities import search_entities
from retrieval.fusion import fuse

REPORT_PATH = Path("notebooks/phase3_retrieval/fusion_weight_sweep.json")
ENTITY_WEIGHTS = [0.0, 0.1, 0.25, 0.5, 1.0]
_TIMEOUT = 120


def mean(values: list) -> float | None:
    present = [v for v in values if v is not None]
    return statistics.mean(present) if present else None


def fmt(v: float | None) -> str:
    return f"{v:.3f}" if v is not None else "  -  "


def main(k: int) -> int:
    load_dotenv()
    settings = RetrievalSettings(top_k=k)
    bedrock = boto3.client("bedrock-runtime", region_name=BedrockSettings().region, config=Config(read_timeout=_TIMEOUT))
    provider = build_provider(EmbeddingSettings(), bedrock)
    client = OpenSearch(hosts=[{"host": "localhost", "port": 9200}], timeout=_TIMEOUT)

    questions = [json.loads(x) for x in Path("data/golden_dataset.jsonl").read_text().splitlines() if x.strip()]
    answerable = [q for q in questions if q.get("expected_behavior") == "answer"]

    session_factory = get_session_factory(get_engine(PostgresSettings()))
    with session_factory() as session:
        chunks_by_paper = defaultdict(list)
        for chunk in session.query(Chunk).all():
            chunks_by_paper[chunk.arxiv_id].append((chunk.chunk_id, chunk.text))

    size = max(settings.over_fetch_multiplier * k, settings.min_candidates)
    cached = []
    for q in answerable:
        relevant: set[str] = set()
        for ev in q["evidence"]:
            if ev.get("quote"):
                relevant |= relevant_chunk_ids(ev["quote"], chunks_by_paper.get(ev["arxiv_id"], []))
        if not relevant:
            continue
        query = q["question"]
        cached.append(
            (
                q,
                relevant,
                {
                    "bm25": search_bm25(client, "evalv1", query, size),
                    "dense_chunks": search_dense_chunks(client, "evalv1", provider, query, size),
                    "dense_claims": search_dense_claims(client, "evalv1", provider, query, size),
                    "entities": search_entities(client, "evalv1", query, size, settings.entity_damping),
                },
            )
        )
        print(f"retrieved {q['id']}", flush=True)

    print(f"\n{len(cached)} questions cached; sweeping without further embedding\n")
    print(f"{'entity weight':>14}{'recall@k':>10}{'ndcg@k':>10}{'entity_anchored':>18}{'multi_paper':>13}")
    rows = []
    for weight in ENTITY_WEIGHTS:
        weights = {"bm25": 1.0, "dense_chunks": 1.0, "dense_claims": 1.0, "entities": weight}
        recalls, ndcgs, by_type = [], [], defaultdict(list)
        for q, relevant, hits in cached:
            fused = fuse(hits, weights=weights, top_k=k)
            ranked = [h.doc_id for h in fused]
            r = recall_at_k(ranked, relevant, k)
            recalls.append(r)
            ndcgs.append(ndcg_at_k(ranked, relevant, k))
            by_type[q["type"]].append(r)
        row = {
            "entity_weight": weight,
            "recall": mean(recalls),
            "ndcg": mean(ndcgs),
            "by_type": {t: mean(v) for t, v in by_type.items()},
        }
        rows.append(row)
        print(
            f"{weight:>14}{fmt(row['recall']):>10}{fmt(row['ndcg']):>10}"
            f"{fmt(row['by_type'].get('entity_anchored')):>18}{fmt(row['by_type'].get('multi_paper')):>13}"
        )

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps({"k": k, "questions": len(cached), "results": rows}, indent=2) + "\n")
    print(f"\nreport: {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=10)
    args = ap.parse_args()
    sys.exit(main(args.k))
