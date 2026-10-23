"""Retrieval Evaluation and Benchmark Suite for PayGuard AI RAG Engine.

Evaluates lexical, semantic, and hybrid retrieval across 8 payment problem categories:
1. Pending Payments
2. Gateway Timeouts
3. Declined Payments & Processor Return Codes
4. Duplicate Charges & Concurrent Authorizations
5. Authorization Holds & Statement Timelines
6. Refund Delays & Acquirer Reference Numbers (ARN)
7. Chargebacks, Disputes, & 3DS Liability Shifts
8. Inconsistent Webhook Events & Ledger Gaps

Metrics computed:
- Hit@1 (Precision@1)
- Hit@3 / Recall@3
- Hit@5 / Recall@5
- Mean Reciprocal Rank (MRR)
"""

import asyncio
from dataclasses import dataclass
import logging
import os
import sys
from typing import Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from backend.app.core.config import settings
from backend.app.services.embedding import MockEmbeddingProvider, get_embedding_provider
from backend.app.services.retrieval import HybridRetrievalService

logger = logging.getLogger("payguard.eval")


@dataclass
class EvalCase:
    category: str
    query: str
    expected_source_id: str
    key_terms: List[str]
    description: str


# Golden benchmark dataset for payment triage retrieval evaluation
EVALUATION_DATASET: List[EvalCase] = [
    EvalCase(
        category="pending_payments",
        query="Why is my payment transaction pending after several days without capturing?",
        expected_source_id="internal://policies/merchant-billing-duplicate-holds",
        key_terms=["pending", "authorization", "expire"],
        description="Customer asking about lingering pending status and hold expiration.",
    ),
    EvalCase(
        category="gateway_timeouts",
        query="Payment gateway timeout upstream connection disconnected after 30 seconds",
        expected_source_id="internal://policies/payment-operations-standard-operating-procedures",
        key_terms=["timeout", "gateway", "network", "status check"],
        description="Gateway network socket disconnection requiring PSP sync.",
    ),
    EvalCase(
        category="declined_codes",
        query="ACH debit transaction failed with return reason code R01 insufficient funds",
        expected_source_id="internal://policies/nacha-ach-return-codes",
        key_terms=["R01", "insufficient funds", "NACHA"],
        description="ACH debit return code R01 re-initiation rules under NACHA.",
    ),
    EvalCase(
        category="duplicate_charges",
        query="Customer was charged twice for identical amounts within 60 seconds duplicate charge",
        expected_source_id="internal://policies/merchant-billing-duplicate-holds",
        key_terms=["duplicate", "concurrent", "60 seconds", "void"],
        description="Duplicate debit attempts within 60-second window.",
    ),
    EvalCase(
        category="authorization_holds",
        query="When will the card authorization hold be released on customer bank statement?",
        expected_source_id="internal://policies/merchant-billing-duplicate-holds",
        key_terms=["authorization hold", "3 to 7 business days", "statement"],
        description="Uncaptured hold timeline differences for credit vs debit cards.",
    ),
    EvalCase(
        category="refund_delays",
        query="Customer has not received their credit card refund after 7 business days ARN escalation",
        expected_source_id="internal://policies/refund-sla-arn-tracing",
        key_terms=["refund", "ARN", "Acquirer Reference Number", "escalation"],
        description="Delayed refund tracking using Acquirer Reference Number (ARN).",
    ),
    EvalCase(
        category="chargebacks_disputes",
        query="Visa dispute reason code 10.4 EMV 3-D Secure liability shift CAVV",
        expected_source_id="internal://policies/visa-dispute-10-4",
        key_terms=["10.4", "liability shift", "CAVV", "3D Secure"],
        description="Visa fraud dispute remedy using 3DS authentication CAVV proof.",
    ),
    EvalCase(
        category="inconsistent_events",
        query="Missing webhook event ledger mismatch between gateway and internal database",
        expected_source_id="internal://policies/payment-operations-standard-operating-procedures",
        key_terms=["webhook", "reconciliation", "PSP", "ledger"],
        description="Dropped webhook sync requiring manual reconciliation with processor.",
    ),
]


@dataclass
class EvalResult:
    category: str
    query: str
    expected_source_id: str
    retrieval_mode: str
    found: bool
    rank: Optional[int]
    reciprocal_rank: float
    top_title: str
    top_source_id: str
    fusion_score: float


@dataclass
class BenchmarkSummary:
    total_queries: int
    retrieval_mode: str
    hit_at_1: float
    hit_at_3: float
    hit_at_5: float
    mrr: float
    results: List[EvalResult]
    provider_status: str


async def run_evaluation(
    session: AsyncSession,
    retrieval_mode: str = "hybrid",
    top_k: int = 5,
    custom_provider=None,
) -> BenchmarkSummary:
    """Runs evaluation benchmark over the 8 payment problem categories."""
    provider = custom_provider or get_embedding_provider()
    provider_status = f"{provider.model_name} (Active)" if provider.is_available else "Lexical Fallback (No Credentials)"

    retrieval_service = HybridRetrievalService(
        session=session,
        embedding_provider=provider,
    )

    results: List[EvalResult] = []

    for case in EVALUATION_DATASET:
        search_res = await retrieval_service.search(
            query=case.query,
            top_k=top_k,
            retrieval_mode=retrieval_mode,
        )

        found_rank = None
        for idx, item in enumerate(search_res.results, start=1):
            if item.source_id == case.expected_source_id:
                found_rank = idx
                break

        rr = 1.0 / found_rank if found_rank is not None else 0.0
        top_item = search_res.results[0] if search_res.results else None

        results.append(
            EvalResult(
                category=case.category,
                query=case.query,
                expected_source_id=case.expected_source_id,
                retrieval_mode=search_res.retrieval_mode,
                found=found_rank is not None,
                rank=found_rank,
                reciprocal_rank=rr,
                top_title=top_item.title if top_item else "None",
                top_source_id=top_item.source_id if top_item else "None",
                fusion_score=top_item.ranking.fusion_score if top_item else 0.0,
            )
        )

    n = len(results)
    hit_1 = sum(1 for r in results if r.rank == 1) / n
    hit_3 = sum(1 for r in results if r.rank is not None and r.rank <= 3) / n
    hit_5 = sum(1 for r in results if r.rank is not None and r.rank <= 5) / n
    mrr = sum(r.reciprocal_rank for r in results) / n

    return BenchmarkSummary(
        total_queries=n,
        retrieval_mode=retrieval_mode,
        hit_at_1=round(hit_1, 4),
        hit_at_3=round(hit_3, 4),
        hit_at_5=round(hit_5, 4),
        mrr=round(mrr, 4),
        results=results,
        provider_status=provider_status,
    )


def print_evaluation_report(summary: BenchmarkSummary):
    """Outputs a formatted ASCII benchmark evaluation report."""
    print("=" * 105)
    print("PAYGUARD AI - RAG RETRIEVAL ENGINE EVALUATION BENCHMARK")
    print("=" * 105)
    print(f"Mode Evaluated   : {summary.retrieval_mode.upper()}")
    print(f"Embedding Provider: {summary.provider_status}")
    print(f"Total Test Cases : {summary.total_queries} queries across 8 payment problem categories")
    print("-" * 105)
    print(f"{'Category':<22} | {'Rank':<5} | {'RR':<6} | {'Top Retrieved Title':<38} | {'Score':<8}")
    print("-" * 105)

    for r in summary.results:
        rank_str = str(r.rank) if r.rank else "MISS"
        rr_str = f"{r.reciprocal_rank:.3f}"
        title_str = (r.top_title[:35] + "...") if len(r.top_title) > 35 else r.top_title
        print(f"{r.category:<22} | {rank_str:<5} | {rr_str:<6} | {title_str:<38} | {r.fusion_score:<.6f}")

    print("-" * 105)
    print(f"SUMMARY METRICS:")
    print(f"  Hit@1 (Precision@1) : {summary.hit_at_1 * 100:.1f}%")
    print(f"  Hit@3 (Recall@3)    : {summary.hit_at_3 * 100:.1f}%")
    print(f"  Hit@5 (Recall@5)    : {summary.hit_at_5 * 100:.1f}%")
    print(f"  Mean Reciprocal Rank: {summary.mrr:.4f}")
    print("=" * 105)


async def main():
    database_url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://payguard_user:payguard_secure_password@localhost:5434/payguard_db",
    )
    print(f"Connecting to database: {database_url}...")
    engine = create_async_engine(database_url, poolclass=NullPool)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        # 1. Evaluate Lexical Mode
        print("\n--- Evaluating Lexical Retrieval Mode ---")
        lexical_summary = await run_evaluation(session, retrieval_mode="lexical_only", top_k=5)
        print_evaluation_report(lexical_summary)

        # 2. Evaluate Hybrid Mode
        print("\n--- Evaluating Hybrid Retrieval Mode ---")
        hybrid_summary = await run_evaluation(session, retrieval_mode="hybrid", top_k=5)
        print_evaluation_report(hybrid_summary)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
