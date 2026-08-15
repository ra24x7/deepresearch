"""Claim + entity enrichment for papers already in Postgres (LIVE Bedrock calls).

Thin driver over src/pipeline — the same stage function the Airflow DAG calls.
Writes a claim spot-check sheet for the user to grade; claim quality sign-off
is the user's alone.

    uv run python scripts/enrich_golden.py 2602.03442 2606.21649 ...
"""

import argparse
import random
import sys
from functools import partial
from pathlib import Path

import boto3
from botocore.config import Config
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config import BedrockSettings, PostgresSettings
from db.models import Claim
from db.session import get_engine, get_session_factory
from llm.bedrock import Usage, invoke_json
from llm.cost import CostLedger
from pipeline.stages import default_pipeline_settings, enrich_paper

SPOTCHECK_PATH = Path("notebooks/phase2_ingestion/claim_spotcheck.md")
SPOTCHECK_SAMPLE = 20
_REQUEST_TIMEOUT_SECONDS = 120


def write_spotcheck(session) -> int:
    claims = session.query(Claim).order_by(Claim.claim_hash).all()
    sample = random.Random(42).sample(claims, min(SPOTCHECK_SAMPLE, len(claims)))
    lines = [
        "# Claim spot-check (Gate A)",
        "",
        "Grade each claim: is it a faithful, atomic statement supported by the paper?",
        "Mark [s] supported / [u] unsupported / [v] vague. Only the user's grades count.",
        "",
    ]
    for i, claim in enumerate(sample, 1):
        lines.append(f"{i}. [ ] ({claim.arxiv_id}, {claim.section_title})")
        lines.append(f"   {claim.claim_text}")
        lines.append("")
    SPOTCHECK_PATH.write_text("\n".join(lines))
    return len(sample)


def main(arxiv_ids: list[str]) -> int:
    load_dotenv()
    settings = default_pipeline_settings()
    client = boto3.client(
        "bedrock-runtime",
        region_name=BedrockSettings().region,
        config=Config(read_timeout=_REQUEST_TIMEOUT_SECONDS, connect_timeout=_REQUEST_TIMEOUT_SECONDS),
    )
    llm = partial(invoke_json, client=client, settings=settings.enrichment)
    session_factory = get_session_factory(get_engine(PostgresSettings()))

    ledger = CostLedger()
    processed = 0
    failures: list[str] = []
    with session_factory() as session:
        for i, arxiv_id in enumerate(arxiv_ids, 1):
            try:
                stats = enrich_paper(arxiv_id, session, lambda p: llm(p), settings)
            except Exception as exc:  # noqa: BLE001 — one paper must not abort a paid batch
                session.rollback()
                failures.append(f"{arxiv_id}: {exc}")
                print(f"[{i}/{len(arxiv_ids)}] {arxiv_id}: FAILED — {exc}", flush=True)
                continue
            ledger = ledger.add(Usage(stats["input_tokens"], stats["output_tokens"]), settings.enrichment.model_id)
            processed += 1
            warn = f"  WARNING: {stats['warning']}" if stats.get("warning") else ""
            print(
                f"[{i}/{len(arxiv_ids)}] {arxiv_id}: {stats['claims']} new claims, "
                f"{stats['entities']} entities, {stats['links']} chunk links{warn}",
                flush=True,
            )
        n_sampled = write_spotcheck(session)

    print(f"\ntokens: {ledger.input_tokens} in / {ledger.output_tokens} out")
    print(f"total cost: ${ledger.total_usd:.4f}  per paper: ${ledger.per_paper_usd(processed):.4f}")
    print(f"spot-check sheet ({n_sampled} claims): {SPOTCHECK_PATH}")
    for line in failures:
        print(f"  failed: {line}")
    return 1 if failures else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("arxiv_ids", nargs="+")
    args = ap.parse_args()
    sys.exit(main(args.arxiv_ids))
