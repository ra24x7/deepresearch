"""Run report: aggregate per-paper stats into one ingestion_runs row.

cost_per_paper_usd is a tracked number (Phase 2 exit criterion), computed from
measured token usage rather than estimated.
"""

from dag_tasks.common import session_factory
from db.models import IngestionRun
from llm.cost import CostLedger
from llm.bedrock import Usage


def _sum(stats: list[dict], key: str) -> int:
    return sum(row.get(key, 0) or 0 for row in stats if isinstance(row, dict))


def write_run_report(**context) -> dict:
    ti = context["ti"]
    parse_stats = [s for s in (ti.xcom_pull(task_ids="parse_and_chunk") or []) if s]
    enrich_stats = [s for s in (ti.xcom_pull(task_ids="enrich") or []) if s]
    index_stats = [s for s in (ti.xcom_pull(task_ids="embed_and_index") or []) if s]
    entity_stats = ti.xcom_pull(task_ids="index_entities") or {}

    papers = len(parse_stats)
    ledger = CostLedger()
    for row in enrich_stats:
        ledger = ledger.add(Usage(input_tokens=row.get("input_tokens", 0), output_tokens=row.get("output_tokens", 0)))

    failures = [
        {"arxiv_id": row["arxiv_id"], "errors": row["errors"][:3]}
        for row in index_stats
        if row.get("errors")
    ]
    warnings = [
        {"arxiv_id": row["arxiv_id"], "warning": row["warning"]} for row in enrich_stats if row.get("warning")
    ]

    run = IngestionRun(
        run_id=context["run_id"],
        corpus=context["params"]["corpus"],
        papers_processed=papers,
        chunks_indexed=_sum(index_stats, "chunks_indexed"),
        claims_indexed=_sum(index_stats, "claims_indexed"),
        entities_upserted=entity_stats.get("entities_indexed", 0),
        llm_input_tokens=ledger.input_tokens,
        llm_output_tokens=ledger.output_tokens,
        total_cost_usd=ledger.total_usd,
        cost_per_paper_usd=ledger.per_paper_usd(papers) if papers else 0.0,
        duration_s=(context["dag_run"].end_date - context["dag_run"].start_date).total_seconds()
        if context["dag_run"].end_date
        else 0.0,
        failures=failures + warnings,
    )
    with session_factory()() as session:
        session.merge(run)
        session.commit()

    summary = {
        "papers": papers,
        "chunks_indexed": run.chunks_indexed,
        "claims_indexed": run.claims_indexed,
        "entities": run.entities_upserted,
        "total_cost_usd": round(run.total_cost_usd, 4),
        "cost_per_paper_usd": round(run.cost_per_paper_usd, 5),
        "failures": len(failures),
    }
    print(f"run report: {summary}", flush=True)
    return summary
