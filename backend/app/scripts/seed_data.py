"""PayGuard AI: Synthetic Dataset and Knowledge Base Seeder.

Loads reproducible, deterministic synthetic payments, event telemetry,
demonstration users, and authoritative policy documents for local development and triage testing.

Idempotent: Can be run multiple times safely without creating duplicate records.
Usage:
    python -m backend.app.scripts.seed_data
    python -m backend.app.scripts.seed_data --reset
"""

import argparse
import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import logging
import os
import sys
from typing import List, Optional
import uuid

# Ensure repository root is on sys.path for CLI execution
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import AsyncSessionLocal
from backend.app.core.security import get_password_hash
from backend.app.models.audit import AuditEvent
from backend.app.models.knowledge import DocumentChunk, KnowledgeDocument
from backend.app.models.payment import Payment, PaymentEvent
from backend.app.models.user import User
from backend.app.services.embedding import (
    IEmbeddingProvider,
    get_embedding_provider,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("payguard.seeder")


# ---------------------------------------------------------------------------
# 1. Demonstration Users
# ---------------------------------------------------------------------------
DEMO_USERS = [
    {
        "email": "agent@payguard.ai",
        "full_name": "Sarah Chen (Support Agent)",
        "role": "support_agent",
        "password": "Password123!",
    },
    {
        "email": "compliance@payguard.ai",
        "full_name": "Marcus Vance (Compliance Analyst)",
        "role": "compliance_analyst",
        "password": "Password123!",
    },
    {
        "email": "admin@payguard.ai",
        "full_name": "Elena Rostova (System Admin)",
        "role": "admin",
        "password": "Password123!",
    },
]


# ---------------------------------------------------------------------------
# 2. Synthetic Payments & Scenarios (40+ Records)
# ---------------------------------------------------------------------------
def generate_synthetic_payments():
    base_time = datetime(2026, 10, 20, 12, 0, 0, tzinfo=timezone.utc)
    payments_data = []

    # Scenario 1: Successful captured card payments (8 records)
    for i in range(1, 9):
        payments_data.append({
            "ref": f"tx_success_{1000 + i}",
            "customer_id": f"cust_us_{100 + i}",
            "merchant_id": "merch_acme_corp",
            "amount": Decimal(f"{25.00 * i:.2f}"),
            "currency": "USD",
            "method": "credit_card",
            "status": "captured",
            "gateway": "stripe",
            "gw_tx_id": f"ch_stripe_succ_{1000 + i}",
            "failure_code": None,
            "failure_msg": None,
            "metadata": {"card_last4": f"{1000 + i}", "card_brand": "Visa", "3ds_authenticated": True},
            "auth_at": base_time - timedelta(days=i, hours=2),
            "cap_at": base_time - timedelta(days=i, hours=1, minutes=45),
            "events": [
                {"type": "authorization_attempt", "from": None, "to": "authorized", "delta_m": -120},
                {"type": "capture_processed", "from": "authorized", "to": "captured", "delta_m": -105},
            ]
        })

    # Scenario 2: Pending payments (batch settlement & clearing delay) (5 records)
    for i in range(1, 6):
        payments_data.append({
            "ref": f"tx_pending_{2000 + i}",
            "customer_id": f"cust_uk_{200 + i}",
            "merchant_id": "merch_saas_cloud",
            "amount": Decimal(f"{99.00 * i:.2f}"),
            "currency": "USD",
            "method": "ach" if i % 2 == 0 else "credit_card",
            "status": "pending",
            "gateway": "stripe",
            "gw_tx_id": f"ch_stripe_pend_{2000 + i}",
            "failure_code": None,
            "failure_msg": None,
            "metadata": {"clearing_window_hours": 48, "rail": "NACHA_ACH" if i % 2 == 0 else "VisaNet"},
            "auth_at": base_time - timedelta(hours=i * 6),
            "cap_at": None,
            "events": [
                {"type": "authorization_initiated", "from": None, "to": "pending", "delta_m": - (i * 360)},
            ]
        })

    # Scenario 3: Declined payments (card expired / do not honor) (6 records)
    decline_reasons = [
        ("card_expired", "The card expiration date is in the past."),
        ("do_not_honor", "Customer bank declined transaction with generic Do Not Honor code 05."),
        ("insufficient_funds", "Account balance insufficient to complete debit."),
        ("stolen_card", "Pick up card - stolen card reported by issuer."),
        ("cvv_mismatch", "Card verification value (CVV2) check failed."),
        ("restricted_card", "Cardholder account is restricted from cross-border charges."),
    ]
    for i, (code, msg) in enumerate(decline_reasons, start=1):
        payments_data.append({
            "ref": f"tx_declined_{3000 + i}",
            "customer_id": f"cust_decl_{300 + i}",
            "merchant_id": "merch_retail_direct",
            "amount": Decimal(f"{75.50 + i * 15:.2f}"),
            "currency": "USD",
            "method": "debit_card",
            "status": "failed",
            "gateway": "adyen",
            "gw_tx_id": f"psp_adyen_{3000 + i}",
            "failure_code": code,
            "failure_msg": msg,
            "metadata": {"refusal_reason": code, "attempt_count": 1},
            "auth_at": base_time - timedelta(days=1, hours=i),
            "cap_at": None,
            "events": [
                {"type": "authorization_attempt", "from": None, "to": "pending", "delta_m": - (60 + i * 10)},
                {"type": "gateway_decline", "from": "pending", "to": "failed", "delta_m": - (59 + i * 10), "payload": {"code": code, "message": msg}},
            ]
        })

    # Scenario 4: Gateway Timeouts / Network Disconnects (4 records)
    for i in range(1, 5):
        payments_data.append({
            "ref": f"tx_timeout_{4000 + i}",
            "customer_id": f"cust_eu_{400 + i}",
            "merchant_id": "merch_global_shop",
            "amount": Decimal(f"{310.00 + i * 20:.2f}"),
            "currency": "EUR",
            "method": "upi" if i % 2 == 0 else "credit_card",
            "status": "failed",
            "gateway": "stripe",
            "gw_tx_id": f"ch_timeout_{4000 + i}",
            "failure_code": "gateway_timeout",
            "failure_msg": "Upstream processor connection timed out after 30000ms.",
            "metadata": {"timeout_ms": 30000, "network_status": "disconnected"},
            "auth_at": base_time - timedelta(hours=i * 3),
            "cap_at": None,
            "events": [
                {"type": "authorization_attempt", "from": None, "to": "pending", "delta_m": - (i * 180)},
                {"type": "network_timeout", "from": "pending", "to": "failed", "delta_m": - (i * 180 - 1), "payload": {"error": "SOCKET_TIMEOUT"}},
            ]
        })

    # Scenario 5: Duplicate Payment Attempts (3 pairs = 6 records)
    for i in range(1, 4):
        # First charge (settled)
        payments_data.append({
            "ref": f"tx_dup_orig_{5000 + i}",
            "customer_id": f"cust_dup_{500 + i}",
            "merchant_id": "merch_subscription_hub",
            "amount": Decimal("149.00"),
            "currency": "USD",
            "method": "credit_card",
            "status": "captured",
            "gateway": "stripe",
            "gw_tx_id": f"ch_orig_{5000 + i}",
            "failure_code": None,
            "failure_msg": None,
            "metadata": {"invoice_id": f"inv_annual_2026_{i}"},
            "auth_at": base_time - timedelta(days=2, minutes=10),
            "cap_at": base_time - timedelta(days=2, minutes=8),
            "events": [
                {"type": "authorization_attempt", "from": None, "to": "authorized", "delta_m": -2890},
                {"type": "capture_processed", "from": "authorized", "to": "captured", "delta_m": -2888},
            ]
        })
        # Second duplicate charge within 15 seconds (unsettled hold)
        payments_data.append({
            "ref": f"tx_dup_hold_{5000 + i}",
            "customer_id": f"cust_dup_{500 + i}",
            "merchant_id": "merch_subscription_hub",
            "amount": Decimal("149.00"),
            "currency": "USD",
            "method": "credit_card",
            "status": "authorized",
            "gateway": "stripe",
            "gw_tx_id": f"ch_dup_{5000 + i}",
            "failure_code": None,
            "failure_msg": None,
            "metadata": {"invoice_id": f"inv_annual_2026_{i}", "duplicate_of": f"tx_dup_orig_{5000 + i}", "hold_window_hours": 72},
            "auth_at": base_time - timedelta(days=2, minutes=9, seconds=45),
            "cap_at": None,
            "events": [
                {"type": "authorization_attempt", "from": None, "to": "authorized", "delta_m": -2889},
            ]
        })

    # Scenario 6: Refunds Pending & Completed (6 records)
    for i in range(1, 4):
        # Refund completed
        payments_data.append({
            "ref": f"tx_ref_done_{6000 + i}",
            "customer_id": f"cust_ref_{600 + i}",
            "merchant_id": "merch_electronics_depot",
            "amount": Decimal(f"{199.99 * i:.2f}"),
            "currency": "USD",
            "method": "credit_card",
            "status": "refunded",
            "gateway": "stripe",
            "gw_tx_id": f"ch_ref_{6000 + i}",
            "failure_code": None,
            "failure_msg": None,
            "metadata": {"refund_arn": f"745123420261020{i}001", "refund_reason": "customer_return"},
            "auth_at": base_time - timedelta(days=10),
            "cap_at": base_time - timedelta(days=10),
            "events": [
                {"type": "captured", "from": "authorized", "to": "captured", "delta_m": -14400},
                {"type": "refund_initiated", "from": "captured", "to": "partially_refunded", "delta_m": -4320},
                {"type": "refund_cleared", "from": "partially_refunded", "to": "refunded", "delta_m": -1440},
            ]
        })
        # Refund pending
        payments_data.append({
            "ref": f"tx_ref_pend_{6000 + i}",
            "customer_id": f"cust_ref_{600 + i}",
            "merchant_id": "merch_electronics_depot",
            "amount": Decimal(f"{89.50 * i:.2f}"),
            "currency": "USD",
            "method": "ach",
            "status": "pending",
            "gateway": "adyen",
            "gw_tx_id": f"psp_ref_pend_{6000 + i}",
            "failure_code": None,
            "failure_msg": None,
            "metadata": {"reversal_requested": True, "ach_return_window_days": 5},
            "auth_at": base_time - timedelta(days=2),
            "cap_at": base_time - timedelta(days=2),
            "events": [
                {"type": "captured", "from": "authorized", "to": "captured", "delta_m": -2880},
                {"type": "refund_initiated", "from": "captured", "to": "pending", "delta_m": -360},
            ]
        })

    # Scenario 7: Inconsistent/Incomplete event history & Chargebacks (5 records)
    for i in range(1, 6):
        payments_data.append({
            "ref": f"tx_disputed_{7000 + i}",
            "customer_id": f"cust_dispute_{700 + i}",
            "merchant_id": "merch_luxury_apparel",
            "amount": Decimal(f"{450.00 * i:.2f}"),
            "currency": "USD",
            "method": "credit_card",
            "status": "disputed",
            "gateway": "stripe",
            "gw_tx_id": f"ch_disp_{7000 + i}",
            "failure_code": "chargeback_condition_10_4",
            "failure_msg": "Visa Dispute Condition 10.4: Other Fraud - Card-Absent Environment.",
            "metadata": {"dispute_id": f"dp_visa_104_{i}", "evidence_deadline": (base_time + timedelta(days=14)).isoformat()},
            "auth_at": base_time - timedelta(days=15),
            "cap_at": base_time - timedelta(days=15),
            "events": [
                {"type": "captured", "from": "authorized", "to": "captured", "delta_m": -21600},
                {"type": "dispute_received", "from": "captured", "to": "disputed", "delta_m": -1200, "payload": {"scheme": "Visa", "reason_code": "10.4"}},
            ]
        })

    return payments_data


# ---------------------------------------------------------------------------
# 3. Sample Policy & Troubleshooting Documents
# ---------------------------------------------------------------------------
SAMPLE_DOCUMENTS = [
    {
        "title": "Visa Core Rules: Dispute Condition 10.4 (Card-Absent Fraud)",
        "source_id": "internal://policies/visa-dispute-10-4",
        "doc_type": "scheme_rules",
        "version": "2026.1",
        "source_url": "https://usa.visa.com/content/dam/VCOM/download/about-visa/visa-rules-public.pdf",
        "chunks": [
            {
                "section": "10.4 Overview & Conditions",
                "content": (
                    "Dispute Condition 10.4 applies when a cardholder asserts they neither participated in nor authorized "
                    "a transaction conducted in a card-absent environment (e-commerce or mail/telephone order). "
                    "The dispute must be submitted within 120 calendar days of the transaction processing date."
                ),
            },
            {
                "section": "10.4 Merchant Remedy & 3D Secure Liability Shift",
                "content": (
                    "If the transaction was authenticated using EMV 3-D Secure (3DS version 2.2 or higher) and the issuer returned "
                    "an Electronic Commerce Indicator (ECI) of 05 or 06, liability shifts to the issuing bank. "
                    "The merchant must provide the 3DS Authentication Verification Value (CAVV) and Transaction ID (Directory Server Trans ID) "
                    "to invalidate the dispute. No chargeback liability applies to the merchant."
                ),
            },
        ],
    },
    {
        "title": "NACHA Operating Rules: ACH Return Reason Codes Guide",
        "source_id": "internal://policies/nacha-ach-return-codes",
        "doc_type": "scheme_rules",
        "version": "2026.2",
        "source_url": "https://www.nacha.org/rules",
        "chunks": [
            {
                "section": "R01 Insufficient Funds & R02 Account Closed",
                "content": (
                    "Return Code R01 indicates that the available balance in the receiver's account is insufficient to cover the debit entry. "
                    "The Originator may re-initiate the debit entry up to two additional times within 180 days. "
                    "Return Code R02 indicates the account was previously closed. Re-initiation is strictly prohibited under NACHA rules."
                ),
            },
            {
                "section": "R08 Payment Stopped & R10 Customer Advises Not Authorized",
                "content": (
                    "Return Code R08 occurs when the receiver requests their Receiving Depository Financial Institution (RDFI) to stop payment on a specific item. "
                    "Return Code R10 signifies the receiver signed a Written Statement of Unauthorized Debit (WSUD). "
                    "The return must be initiated within 60 days of the settlement date. The merchant must seek alternative settlement directly with the customer."
                ),
            },
        ],
    },
    {
        "title": "Merchant Billing Policy: Authorization Holds and Duplicate Debits",
        "source_id": "internal://policies/merchant-billing-duplicate-holds",
        "doc_type": "refund_policy",
        "version": "1.4",
        "source_url": "https://internal.payguard.ai/docs/merchant-billing-policy-v1.4.md",
        "chunks": [
            {
                "section": "Section 4.1: Concurrent Submission & Duplicate Detection",
                "content": (
                    "When two or more authorization attempts occur for identical amounts from the same customer within 60 seconds, "
                    "the secondary authorization is categorized as a duplicate hold. "
                    "If the primary charge captures successfully, the secondary authorization must be released immediately using the gateway void API."
                ),
            },
            {
                "section": "Section 4.2: Cardholder Statement Timelines",
                "content": (
                    "Uncaptured authorization holds automatically expire based on issuing bank policies: "
                    "Typically 3 to 7 business days for credit cards, and up to 10 business days for debit cards. "
                    "Operations engineers should advise customers that pending holds do not represent actual debited funds and require no refund action."
                ),
            },
        ],
    },
    {
        "title": "Platform Refund Lifecycle & Acquirer Reference Number (ARN) Guidelines",
        "source_id": "internal://policies/refund-sla-arn-tracing",
        "doc_type": "sla_spec",
        "version": "2.0",
        "source_url": "https://internal.payguard.ai/docs/refund-sla-2.0.md",
        "chunks": [
            {
                "section": "SLA Reversal Timelines by Rail",
                "content": (
                    "Credit card refunds settle within 3 to 5 business days after issuance. "
                    "ACH direct debit refunds take 5 to 7 business days due to clearinghouse batch cycles. "
                    "Instant rail refunds (UPI, FedNow) reflect in receiver accounts within 15 minutes of status transition to 'refunded'."
                ),
            },
            {
                "section": "ARN Tracing Protocol",
                "content": (
                    "If a customer reports non-receipt of card refund funds after 7 business days, the support engineer must look up the "
                    "23-digit Acquirer Reference Number (ARN) in the gateway payload metadata. "
                    "Providing the ARN to the cardholder enables their issuing bank branch to trace the credit batch directly."
                ),
            },
        ],
    },
    {
        "title": "Payment Operations: SOP for Gateway Timeouts and Reconciliation Gaps",
        "source_id": "internal://policies/payment-operations-standard-operating-procedures",
        "doc_type": "troubleshooting_guide",
        "version": "1.2",
        "source_url": "https://internal.payguard.ai/docs/ops-sop-timeouts-v1.2.md",
        "chunks": [
            {
                "section": "Gateway Timeouts & Upstream Disconnects",
                "content": (
                    "When an upstream processor connection times out after 30000ms (30 seconds), the gateway transition remains pending or failed. "
                    "Support operations engineers must immediately invoke the PSP transaction verification API to check whether authorization captured. "
                    "If the PSP confirms capture, update internal database status to captured to prevent duplicate retries."
                ),
            },
            {
                "section": "Webhook Delivery Gaps & Manual Ledger Reconciliation",
                "content": (
                    "Missing webhook notifications create discrepancies between gateway processor status and internal payment state. "
                    "When a customer card is debited but payment state remains pending or failed, the support engineer must pull the processor event log. "
                    "Perform manual ledger reconciliation by matching the payment reference and acquirer reference number before issuing compensation."
                ),
            },
        ],
    },
]


# ---------------------------------------------------------------------------
# 4. Modular Seed Functions
# ---------------------------------------------------------------------------
async def seed_users(session: AsyncSession) -> list[User]:
    """Idempotently seed demonstration user accounts."""
    results = []
    for user_data in DEMO_USERS:
        stmt = select(User).where(User.email == user_data["email"])
        existing = (await session.execute(stmt)).scalar_one_or_none()
        if not existing:
            user = User(
                id=uuid.uuid4(),
                email=user_data["email"],
                hashed_password=get_password_hash(user_data["password"]),
                full_name=user_data["full_name"],
                role=user_data["role"],
                is_active=True,
            )
            session.add(user)
            results.append(user)
        else:
            results.append(existing)
    await session.commit()
    return results


async def seed_payments_and_events(session: AsyncSession) -> list[Payment]:
    """Idempotently seed synthetic payments and correlated payment event timelines."""
    payments = generate_synthetic_payments()
    results = []
    for p_data in payments:
        stmt = select(Payment).where(Payment.payment_reference == p_data["ref"])
        existing = (await session.execute(stmt)).scalar_one_or_none()
        if not existing:
            payment_id = uuid.uuid4()
            payment = Payment(
                id=payment_id,
                payment_reference=p_data["ref"],
                customer_id=p_data["customer_id"],
                merchant_id=p_data["merchant_id"],
                amount=p_data["amount"],
                currency=p_data["currency"],
                payment_method=p_data["method"],
                status=p_data["status"],
                gateway_name=p_data["gateway"],
                gateway_transaction_id=p_data["gw_tx_id"],
                failure_code=p_data["failure_code"],
                failure_message=p_data["failure_msg"],
                metadata_=p_data["metadata"],
                authorized_at=p_data["auth_at"],
                captured_at=p_data["cap_at"],
            )
            session.add(payment)
            results.append(payment)

            # Add events
            base_time = p_data["auth_at"] or datetime.now(timezone.utc)
            for ev in p_data["events"]:
                event = PaymentEvent(
                    id=uuid.uuid4(),
                    payment_id=payment_id,
                    event_type=ev["type"],
                    from_status=ev.get("from"),
                    to_status=ev["to"],
                    raw_payload=ev.get("payload", {"source": "gateway_webhook", "simulated": True}),
                    occurred_at=base_time + timedelta(minutes=ev["delta_m"]),
                )
                session.add(event)
        else:
            results.append(existing)

    await session.commit()
    return results


async def seed_knowledge_documents(
    session: AsyncSession,
    provider: Optional[IEmbeddingProvider] = None,
) -> list[KnowledgeDocument]:
    """Idempotently seed authoritative policy and troubleshooting documents."""
    import hashlib
    if provider is None:
        provider = get_embedding_provider()

    results = []
    for doc_data in SAMPLE_DOCUMENTS:
        raw_text = "\n\n".join(c["content"] for c in doc_data["chunks"])
        content_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()

        stmt = select(KnowledgeDocument).where(
            (KnowledgeDocument.title == doc_data["title"])
            | (KnowledgeDocument.source_id == doc_data.get("source_id"))
        )
        existing = (await session.execute(stmt)).scalar_one_or_none()
        if not existing:
            doc_id = uuid.uuid4()
            doc = KnowledgeDocument(
                id=doc_id,
                title=doc_data["title"],
                source_id=doc_data.get("source_id"),
                doc_type=doc_data["doc_type"],
                version=doc_data["version"],
                source_url=doc_data["source_url"],
                raw_content=raw_text,
                content_hash=content_hash,
                is_active=True,
            )
            session.add(doc)
            results.append(doc)

            # Generate real provider embeddings if available
            vectors: Optional[List[List[float]]] = None
            if provider.is_available:
                try:
                    texts = [c["content"] for c in doc_data["chunks"]]
                    vectors = await provider.embed_batch(texts)
                except Exception as e:
                    logger.warning(
                        f"Live embedding generation failed during seed for '{doc_data['title']}': {e}. "
                        "Falling back to unverified placeholder vectors."
                    )
                    vectors = None

            for idx, chunk_data in enumerate(doc_data["chunks"]):
                if vectors is not None and idx < len(vectors):
                    chunk_embedding = vectors[idx]
                    chunk_model = provider.model_name
                    provenance = "live_provider_generated"
                else:
                    chunk_embedding = [0.025] * 1536
                    chunk_model = "synthetic_placeholder"
                    provenance = "synthetic_placeholder_unverified"

                chunk = DocumentChunk(
                    id=uuid.uuid4(),
                    document_id=doc_id,
                    chunk_index=idx,
                    section_header=chunk_data["section"],
                    content=chunk_data["content"],
                    token_count=len(chunk_data["content"].split()),
                    embedding=chunk_embedding,
                    embedding_model=chunk_model,
                    metadata_={
                        "provenance": provenance,
                        "version": doc_data["version"],
                        "source_id": doc_data.get("source_id"),
                    },
                )
                session.add(chunk)
        else:
            if not existing.source_id and doc_data.get("source_id"):
                existing.source_id = doc_data["source_id"]
                existing.raw_content = raw_text
                existing.content_hash = content_hash
            results.append(existing)

    await session.commit()
    return results


async def reembed_knowledge_chunks(
    session: AsyncSession,
    provider: Optional[IEmbeddingProvider] = None,
    force: bool = False,
    batch_size: int = 32,
) -> dict:
    """Safely and resumably re-embeds eligible knowledge chunks using the active provider.

    Persists genuine embedding vectors to PostgreSQL and updates chunk metadata.
    Avoids duplicating chunks. Resumable via per-batch database transactions.
    """
    if provider is None:
        provider = get_embedding_provider()

    logger.info(f"Re-embedding workflow initiated with provider model: {provider.model_name}")

    # 1. Total chunk count
    total_stmt = select(func.count(DocumentChunk.id))
    total_chunks = (await session.execute(total_stmt)).scalar_one()

    # 2. Check provider availability
    if not provider.is_available:
        msg = (
            f"Embedding provider '{provider.model_name}' credentials unavailable (OPENAI_API_KEY missing or placeholder). "
            "Live semantic embeddings remain unverified. Existing chunks were not modified."
        )
        logger.warning(msg)
        return {
            "status": "unverified_provider_unavailable",
            "provider": provider.model_name,
            "provider_available": False,
            "total_chunks": total_chunks,
            "eligible_chunks": 0,
            "reembedded": 0,
            "skipped": total_chunks,
            "failed": 0,
            "message": msg,
        }

    # 3. Query eligible chunks
    if force:
        eligible_stmt = (
            select(DocumentChunk)
            .where(
                or_(
                    DocumentChunk.embedding_model != provider.model_name,
                    DocumentChunk.embedding.is_(None),
                    DocumentChunk.embedding_model.is_(None),
                )
            )
            .order_by(DocumentChunk.document_id, DocumentChunk.chunk_index)
        )
    else:
        eligible_stmt = (
            select(DocumentChunk)
            .where(
                or_(
                    DocumentChunk.embedding_model == "synthetic_placeholder",
                    DocumentChunk.embedding.is_(None),
                    DocumentChunk.embedding_model.is_(None),
                )
            )
            .order_by(DocumentChunk.document_id, DocumentChunk.chunk_index)
        )

    eligible_res = await session.execute(eligible_stmt)
    eligible_chunks = list(eligible_res.scalars().all())
    eligible_count = len(eligible_chunks)
    skipped_count = total_chunks - eligible_count

    if not eligible_chunks:
        msg = f"All {total_chunks} chunks already embedded with model '{provider.model_name}'. No re-embedding needed."
        logger.info(msg)
        return {
            "status": "up_to_date",
            "provider": provider.model_name,
            "provider_available": True,
            "total_chunks": total_chunks,
            "eligible_chunks": 0,
            "reembedded": 0,
            "skipped": total_chunks,
            "failed": 0,
            "message": msg,
        }

    logger.info(f"Found {eligible_count} eligible chunks to re-embed ({skipped_count} skipped/up-to-date).")

    reembedded_count = 0
    failed_count = 0

    # 4. Batch processing with transactional per-batch commit for resumability
    for i in range(0, eligible_count, batch_size):
        batch = eligible_chunks[i : i + batch_size]
        texts = [c.content for c in batch]

        try:
            vectors = await provider.embed_batch(texts)
            if len(vectors) != len(batch):
                raise ValueError(f"Vector count mismatch: expected {len(batch)}, got {len(vectors)}")

            for chunk, vec in zip(batch, vectors):
                valid_vec = provider.validate_vector(vec)
                chunk.embedding = valid_vec
                chunk.embedding_model = provider.model_name
                metadata = dict(chunk.metadata_ or {})
                metadata["reembedded_at"] = datetime.now(timezone.utc).isoformat()
                metadata["provenance"] = "live_provider_generated"
                metadata["embedding_model"] = provider.model_name
                chunk.metadata_ = metadata

            await session.commit()
            reembedded_count += len(batch)
            logger.info(f"Progress: {reembedded_count}/{eligible_count} chunks re-embedded and committed.")

        except Exception as e:
            await session.rollback()
            failed_count += len(batch)
            logger.error(
                f"Failed to embed batch starting at index {i}: {e}. "
                "Rolled back batch. Previously committed batches remain safe."
            )
            return {
                "status": "failed",
                "provider": provider.model_name,
                "provider_available": True,
                "total_chunks": total_chunks,
                "eligible_chunks": eligible_count,
                "reembedded": reembedded_count,
                "skipped": skipped_count,
                "failed": failed_count,
                "error": str(e),
                "message": f"Batch re-embedding aborted due to error: {e}",
            }

    msg = f"Successfully re-embedded {reembedded_count} chunks using {provider.model_name}."
    logger.info(msg)
    return {
        "status": "completed",
        "provider": provider.model_name,
        "provider_available": True,
        "total_chunks": total_chunks,
        "eligible_chunks": eligible_count,
        "reembedded": reembedded_count,
        "skipped": skipped_count,
        "failed": 0,
        "message": msg,
    }


async def seed_database(reset: bool = False, session: Optional[AsyncSession] = None):
    """Executes full idempotent database seeding."""
    logger.info("Connecting to database session...")

    async def _execute_seed(s: AsyncSession):
        if reset:
            logger.warning("Reset requested! Truncating core transactional tables...")
            await s.execute(text("TRUNCATE TABLE audit_events, investigation_results, investigation_cases, payment_events, payments, document_chunks, knowledge_documents, users CASCADE;"))
            await s.commit()
            logger.info("Tables truncated successfully.")

        # 1. Users
        logger.info("Seeding demonstration users...")
        users = await seed_users(s)
        logger.info(f"User seeding complete: {len(users)} demo accounts ready.")

        # 2. Payments & Events
        logger.info("Seeding synthetic payment records and event timelines...")
        payments = await seed_payments_and_events(s)
        logger.info(f"Payment seeding complete: {len(payments)} payments ready.")

        # 3. Knowledge Documents
        logger.info("Seeding authoritative policy documents and chunks...")
        docs = await seed_knowledge_documents(s)
        logger.info(f"Document seeding complete: {len(docs)} documents ready.")

        # 4. Audit Log
        audit = AuditEvent(
            id=uuid.uuid4(),
            action="database_seeded",
            resource_type="system",
            resource_id="synthetic_dataset_v1",
            details={
                "users_seeded": len(users),
                "payments_seeded": len(payments),
                "documents_seeded": len(docs),
            },
        )
        s.add(audit)
        await s.commit()
        logger.info("Audit event recorded. Seeding finished successfully!")

    if session:
        await _execute_seed(session)
    else:
        async with AsyncSessionLocal() as s:
            await _execute_seed(s)


def main():
    parser = argparse.ArgumentParser(description="PayGuard AI Database Seeder & Embedding Pipeline")
    parser.add_argument("--reset", action="store_true", help="Truncate tables before seeding")
    parser.add_argument("--reembed-live", action="store_true", help="Re-embed eligible chunks using configured real embedding provider")
    parser.add_argument("--force", action="store_true", help="Force re-embedding all chunks even if already embedded")
    parser.add_argument("--batch-size", type=int, default=32, help="Batch size for re-embedding")
    args = parser.parse_args()

    if args.reembed_live:
        async def _run_reembed():
            async with AsyncSessionLocal() as s:
                report = await reembed_knowledge_chunks(s, force=args.force, batch_size=args.batch_size)
                print("\n=== PAYGUARD RAG RE-EMBEDDING REPORT ===")
                print(f"Status:             {report['status']}")
                print(f"Provider:           {report['provider']}")
                print(f"Provider Available: {report['provider_available']}")
                print(f"Total Chunks:       {report['total_chunks']}")
                print(f"Eligible Chunks:    {report.get('eligible_chunks', 0)}")
                print(f"Re-embedded:        {report['reembedded']}")
                print(f"Skipped:            {report['skipped']}")
                print(f"Failed:             {report['failed']}")
                print(f"Message:            {report['message']}")
                print("=========================================\n")
        asyncio.run(_run_reembed())
    else:
        asyncio.run(seed_database(reset=args.reset))


if __name__ == "__main__":
    main()
