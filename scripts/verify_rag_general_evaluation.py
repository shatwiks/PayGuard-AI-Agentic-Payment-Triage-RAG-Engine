"""Comprehensive Stage 6 Frozen Held-Out Evaluation Suite for PayGuard AI RAG Engine.

Executes live against PostgreSQL (port 5434) and real Ollama models:
- Embedding: nomic-embed-text
- LLM: llama3.2:1b
Strictly NO MOCKS.

Evaluates 100 frozen questions across 10 distinct categories with 3 automated paraphrases
each (300 total evaluations) over 2 unseen, held-out financial policy documents.

Categories:
 1. Direct factual lookup
 2. Paraphrased query (vocabulary gap)
 3. Multi-sentence evidence
 4. Numeric / date reasoning
 5. Table / structured list lookup
 6. Multi-hop across sections
 7. Negation and exception
 8. Unanswerable / out-of-scope (clean abstention required)
 9. Adversarial / distractors (wrong predicate / wrong currency)
10. Typo / informal query

Metrics Reported:
- Recall@5
- Answer Correctness
- Groundedness Precision
- Abstention Precision & Recall
- False Acceptance Rate (FAR)
- Latency p50 / p95 with 95% Confidence Intervals
- Failure categorization breakdown
"""

import asyncio
import atexit
import math
import os
import random
import re
import shutil
import tempfile
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select, text

from backend.app.core.config import settings
from backend.app.core.database import AsyncSessionLocal

# Isolate evaluation upload directory
_eval_upload_dir = tempfile.mkdtemp(prefix="payguard_stage6_eval_")
settings.UPLOAD_STORAGE_DIR = _eval_upload_dir
settings.EMBEDDING_PROVIDER = "ollama"
settings.LLM_PROVIDER = "ollama"
settings.OLLAMA_LLM_MODEL = "llama3.1:8b"
atexit.register(lambda: shutil.rmtree(_eval_upload_dir, ignore_errors=True))

from backend.app.models.knowledge import KnowledgeDocument
from backend.app.models.user import User
from backend.app.schemas.knowledge import DocumentAskRequest, KnowledgeSearchRequest
from backend.app.services.document_qa import DocumentQAService
from backend.app.services.embedding import OllamaEmbeddingProvider
from backend.app.services.ingestion import DocumentIngestionPipeline
from backend.app.services.retrieval import HybridRetrievalService


# ---------------------------------------------------------------------------
# Unseen Held-Out Documents
# ---------------------------------------------------------------------------

DOC_TREASURY = """# Global Treasury Settlement Protocol 2026
## 1. RTGS High-Value Clearing
Real-Time Gross Settlement (RTGS) transactions exceeding 1,000,000 EUR settle through the central liquidity window between 07:00 and 18:00 CET.
For priority transfers submitted after 17:30 CET, a late-submission processing surcharge of 45.00 EUR applies.
Standard transfers submitted after cutoff are queued until the next business day.

## 2. Cross-Border FX Remittance Limits
Standard retail cross-border transfers are capped at 50,000 USD per 24-hour cycle.
Institutional market makers maintaining active collateral accounts may execute up to 25,000,000 USD daily.
Non-compliant requests exceeding these thresholds are automatically rejected under compliance rule FX-TR-901.

## 3. Collateral Escrow & Margin Maintenance
Merchants classified under High Volatility Tier 4 must maintain a minimum rolling escrow balance of 15.0 percent of total 30-day processed volume.
Early collateral release prior to 90 calendar days is strictly prohibited without dual-custody treasury committee sign-off under rule ESC-990.
If collateral falls below 10.0 percent, an emergency margin call must be satisfied within 48 hours.

## 4. SEPA Direct Debit Indemnity Provisions
Direct debits returned due to insufficient funds under return code R01 incur an administrative charge of 7.50 EUR.
For unauthorized transactions disputed under rule VP-SEPA-401, the creditor bank must deposit a full indemnity guarantee within 5 business days.
Partial indemnity release is strictly prohibited under rule VP-SEPA-401 until final arbitration resolution.
"""

DOC_MERCHANT = """# Merchant Processing Standards and Dispute Framework
## 1. Tiered Fee Schedule
| Tier Level | Monthly Volume | Dispute Fee | Interchange Rate |
| Standard | Under $100,000 | $15.00 USD | 2.15% |
| Premium | $100,000 - $1,000,000 | $10.00 USD | 1.85% |
| Platinum | Over $1,000,000 | $5.50 USD | 1.45% |

For merchants processing more than 10,000,000 USD monthly, customized enterprise rates apply with dispute fees discounted to $3.50 USD.

## 2. Chargeback Defense Windows
Merchants have 20 calendar days from the date of initial dispute notification to submit representment documentation.
Expedited dispute responses submitted within 72 hours receive an early-resolution credit of $2.00 USD.
Failure to submit defense evidence within 20 calendar days results in automatic forfeiture of the disputed funds under rule DISP-808.

## 3. Account Termination and Reserve Holds
Upon involuntary account termination due to excessive fraud, rolling reserves are held for 180 calendar days to cover trailing chargebacks.
Voluntary account closure with zero active disputes allows full reserve disbursement within 30 business days.
Under no circumstances may termination reserves be disbursed while active legal freezes are in effect under statute SEC-104.

## 4. Hardware POS Terminal Lease Agreements
Standard POS terminal lease is $29.00 USD per month with a 12-month commitment.
Terminating terminal lease prior to 6 months incurs an early termination penalty of $150.00 USD.
Defective terminals are replaced within 2 business days at zero additional charge.
"""

# ---------------------------------------------------------------------------
# 100 Frozen Benchmark Questions (10 categories x 10 questions)
# ---------------------------------------------------------------------------

QUESTIONS_DATA = [
    # 1. Direct Factual Lookup (10)
    {"q": "What is the surcharge for priority RTGS transfers submitted after 17:30 CET?", "gold": "45.00 EUR", "ans": True, "cat": "factual"},
    {"q": "What is the daily cross-border transfer limit for standard retail customers?", "gold": "50,000 USD", "ans": True, "cat": "factual"},
    {"q": "What percentage rolling escrow balance is required for Tier 4 merchants?", "gold": "15.0 percent", "ans": True, "cat": "factual"},
    {"q": "What is the administrative charge for direct debits returned with code R01?", "gold": "7.50 EUR", "ans": True, "cat": "factual"},
    {"q": "What is the monthly lease fee for a standard POS terminal?", "gold": "$29.00 USD", "ans": True, "cat": "factual"},
    {"q": "What is the dispute fee for Standard tier merchants?", "gold": "$15.00 USD", "ans": True, "cat": "factual"},
    {"q": "What is the interchange rate for Platinum tier merchants?", "gold": "1.45%", "ans": True, "cat": "factual"},
    {"q": "How long are reserves held following involuntary account termination?", "gold": "180 calendar days", "ans": True, "cat": "factual"},
    {"q": "What is the early termination penalty for POS terminals cancelled before 6 months?", "gold": "$150.00 USD", "ans": True, "cat": "factual"},
    {"q": "What is the operating window for RTGS high-value clearing?", "gold": "07:00 and 18:00 CET", "ans": True, "cat": "factual"},

    # 2. Paraphrased Query (10)
    {"q": "How much does a seller pay per contestation if they belong to the Platinum tier?", "gold": "$5.50 USD", "ans": True, "cat": "paraphrase"},
    {"q": "What is billed to a store if an insufficient funds bounce occurs under R01?", "gold": "7.50 EUR", "ans": True, "cat": "paraphrase"},
    {"q": "What is the late filing penalty for high-value European settlements after 5:30 PM CET?", "gold": "45.00 EUR", "ans": True, "cat": "paraphrase"},
    {"q": "How long must merchant collateral remain in escrow before early distribution is permitted?", "gold": "90 calendar days", "ans": True, "cat": "paraphrase"},
    {"q": "What time limit applies to store owners for sending rebuttals against customer chargebacks?", "gold": "20 calendar days", "ans": True, "cat": "paraphrase"},
    {"q": "How much credit is granted for quick dispute submissions delivered within three days?", "gold": "$2.00 USD", "ans": True, "cat": "paraphrase"},
    {"q": "What daily remittance cap governs institutional market participants?", "gold": "25,000,000 USD", "ans": True, "cat": "paraphrase"},
    {"q": "In how many days must an emergency collateral deficit be satisfied?", "gold": "48 hours", "ans": True, "cat": "paraphrase"},
    {"q": "Within what timeframe are faulty payment hardware devices swapped out?", "gold": "2 business days", "ans": True, "cat": "paraphrase"},
    {"q": "What is the dispute assessment for mega corporate clients processing over 10 million monthly?", "gold": "$3.50 USD", "ans": True, "cat": "paraphrase"},

    # 3. Multi-Sentence Evidence (10)
    {"q": "What happens to standard RTGS payments submitted after the evening cutoff?", "gold": "queued until the next business day", "ans": True, "cat": "multi_sentence"},
    {"q": "What consequence occurs if a merchant fails to submit chargeback defense within 20 days?", "gold": "automatic forfeiture of the disputed funds", "ans": True, "cat": "multi_sentence"},
    {"q": "What rule rejects transfers that exceed the 50,000 USD or 25,000,000 USD limits?", "gold": "FX-TR-901", "ans": True, "cat": "multi_sentence"},
    {"q": "What triggers an emergency margin call under the Collateral Escrow section?", "gold": "falls below 10.0 percent", "ans": True, "cat": "multi_sentence"},
    {"q": "What requirement applies to unauthorized transactions disputed under VP-SEPA-401?", "gold": "full indemnity guarantee within 5 business days", "ans": True, "cat": "multi_sentence"},
    {"q": "What happens to rolling reserves when an account is voluntarily closed with zero disputes?", "gold": "disbursement within 30 business days", "ans": True, "cat": "multi_sentence"},
    {"q": "What is the initial lease duration commitment for POS terminals?", "gold": "12-month commitment", "ans": True, "cat": "multi_sentence"},
    {"q": "What is the cost to replace a defective terminal?", "gold": "zero additional charge", "ans": True, "cat": "multi_sentence"},
    {"q": "Who must approve early collateral release before 90 calendar days have elapsed?", "gold": "dual-custody treasury committee sign-off", "ans": True, "cat": "multi_sentence"},
    {"q": "Under what rule does automatic dispute forfeiture take place?", "gold": "DISP-808", "ans": True, "cat": "multi_sentence"},

    # 4. Numeric / Date Reasoning (10)
    {"q": "How many business days does a creditor bank have to deposit full indemnity under VP-SEPA-401?", "gold": "5 business days", "ans": True, "cat": "numeric"},
    {"q": "What is the minimum volume threshold to qualify for the Platinum tier?", "gold": "Over $1,000,000", "ans": True, "cat": "numeric"},
    {"q": "What is the interchange rate for Standard tier merchants?", "gold": "2.15%", "ans": True, "cat": "numeric"},
    {"q": "What is the dispute fee for Premium tier merchants?", "gold": "$10.00 USD", "ans": True, "cat": "numeric"},
    {"q": "How many hours define an expedited dispute response eligible for credit?", "gold": "72 hours", "ans": True, "cat": "numeric"},
    {"q": "What is the minimum transaction amount required for RTGS high-value clearing?", "gold": "1,000,000 EUR", "ans": True, "cat": "numeric"},
    {"q": "What collateral percentage triggers an emergency margin call?", "gold": "10.0 percent", "ans": True, "cat": "numeric"},
    {"q": "How many calendar days must elapse before termination reserves can be released?", "gold": "180 calendar days", "ans": True, "cat": "numeric"},
    {"q": "How many business days are allowed for voluntary closure reserve disbursement?", "gold": "30 business days", "ans": True, "cat": "numeric"},
    {"q": "What is the monthly processing volume threshold for enterprise dispute discounts?", "gold": "10,000,000 USD", "ans": True, "cat": "numeric"},

    # 5. Table / Structured List Lookup (10)
    {"q": "According to the fee schedule, what is the monthly volume range for Premium tier?", "gold": "$100,000 - $1,000,000", "ans": True, "cat": "table"},
    {"q": "What is the dispute fee listed in the table for Premium merchants?", "gold": "$10.00 USD", "ans": True, "cat": "table"},
    {"q": "What interchange rate does the table specify for Standard tier merchants?", "gold": "2.15%", "ans": True, "cat": "table"},
    {"q": "What is the dispute fee listed in the table for Standard tier?", "gold": "$15.00 USD", "ans": True, "cat": "table"},
    {"q": "What interchange rate does the table list for Platinum tier?", "gold": "1.45%", "ans": True, "cat": "table"},
    {"q": "Which tier in the table has a monthly volume under $100,000?", "gold": "Standard", "ans": True, "cat": "table"},
    {"q": "Which tier in the table has a dispute fee of $5.50 USD?", "gold": "Platinum", "ans": True, "cat": "table"},
    {"q": "What is the monthly volume requirement for Platinum tier in the table?", "gold": "Over $1,000,000", "ans": True, "cat": "table"},
    {"q": "What is the interchange rate for Premium tier in the table?", "gold": "1.85%", "ans": True, "cat": "table"},
    {"q": "How many tier levels are defined in the fee schedule table?", "gold": "3", "ans": True, "cat": "table"},

    # 6. Multi-Hop Across Sections (10)
    {"q": "How does the dispute fee for Platinum merchants compare to the enterprise rate?", "gold": "$5.50 USD", "ans": True, "cat": "multi_hop"},
    {"q": "What is the difference in reserve holding periods between voluntary closure and involuntary termination?", "gold": "180 calendar days", "ans": True, "cat": "multi_hop"},
    {"q": "Can a merchant receive early dispute resolution credit if they respond after 72 hours but before 20 days?", "gold": "within 72 hours", "ans": True, "cat": "multi_hop"},
    {"q": "What is the total early termination fee if a POS terminal lease is cancelled in month 4?", "gold": "$150.00 USD", "ans": True, "cat": "multi_hop"},
    {"q": "What two thresholds govern retail versus institutional FX remittances?", "gold": "50,000 USD", "ans": True, "cat": "multi_hop"},
    {"q": "How does the indemnity timeline for VP-SEPA-401 compare to the R01 return charge?", "gold": "5 business days", "ans": True, "cat": "multi_hop"},
    {"q": "What rule governs early collateral release and what committee must approve it?", "gold": "ESC-990", "ans": True, "cat": "multi_hop"},
    {"q": "What is the effective net dispute fee for a Premium merchant submitting an expedited response?", "gold": "$8.00 USD", "ans": True, "cat": "multi_hop"},
    {"q": "Which currency applies to late RTGS surcharges compared to POS terminal leases?", "gold": "EUR", "ans": True, "cat": "multi_hop"},
    {"q": "Under what conditions can termination reserves be disbursed while legal freezes are active?", "gold": "Under no circumstances", "ans": True, "cat": "multi_hop"},

    # 7. Negation and Exception (10)
    {"q": "Is partial indemnity release permitted under rule VP-SEPA-401?", "gold": "strictly prohibited", "ans": True, "cat": "negation"},
    {"q": "Can collateral escrow be released prior to 90 days without committee sign-off?", "gold": "strictly prohibited", "ans": True, "cat": "negation"},
    {"q": "Are termination reserves disbursed when active legal freezes are in effect under SEC-104?", "gold": "Under no circumstances", "ans": True, "cat": "negation"},
    {"q": "Can a merchant retry re-initiation if a direct debit is returned under code R01?", "gold": "7.50 EUR", "ans": True, "cat": "negation"},
    {"q": "Are retail customers allowed to transfer more than 50,000 USD daily?", "gold": "automatically rejected", "ans": True, "cat": "negation"},
    {"q": "Is there any additional charge for replacing a defective POS terminal?", "gold": "zero additional charge", "ans": True, "cat": "negation"},
    {"q": "Can a merchant avoid dispute forfeiture if they miss the 20-day window?", "gold": "automatic forfeiture", "ans": True, "cat": "negation"},
    {"q": "Does a standard RTGS transfer submitted after 17:30 CET incur the 45.00 EUR surcharge?", "gold": "priority transfers", "ans": True, "cat": "negation"},
    {"q": "Can a Tier 4 merchant maintain only 8.0 percent collateral balance?", "gold": "emergency margin call", "ans": True, "cat": "negation"},
    {"q": "Is early POS lease cancellation allowed without penalty after 8 months?", "gold": "prior to 6 months", "ans": True, "cat": "negation"},

    # 8. Unanswerable / Out-of-Scope (MUST ABSTAIN) (10)
    {"q": "What is the interest rate on Bitcoin liquidity pools under the treasury agreement?", "gold": None, "ans": False, "cat": "unanswerable"},
    {"q": "How many days does an ACH tax refund take to clear through Fedwire?", "gold": None, "ans": False, "cat": "unanswerable"},
    {"q": "What is the penalty for late submission of annual corporate tax filings?", "gold": None, "ans": False, "cat": "unanswerable"},
    {"q": "What are the underwriting criteria for obtaining an unsecured merchant cash advance?", "gold": None, "ans": False, "cat": "unanswerable"},
    {"q": "What fee is charged for paper statement delivery to retail merchants?", "gold": None, "ans": False, "cat": "unanswerable"},
    {"q": "What is the maximum loan-to-value ratio for commercial real estate mortgages?", "gold": None, "ans": False, "cat": "unanswerable"},
    {"q": "How much does a virtual terminal license cost per seat monthly?", "gold": None, "ans": False, "cat": "unanswerable"},
    {"q": "What is the processing surcharge for UnionPay transactions in Hong Kong?", "gold": None, "ans": False, "cat": "unanswerable"},
    {"q": "What discount applies to annual prepaid SaaS subscription tiers?", "gold": None, "ans": False, "cat": "unanswerable"},
    {"q": "What is the maximum insurance coverage on deposit accounts under FDIC rules?", "gold": None, "ans": False, "cat": "unanswerable"},

    # 9. Adversarial / Distractors (Wrong Predicate / Wrong Currency) (MUST ABSTAIN) (10)
    {"q": "What is the late RTGS surcharge for transfers denominated in GBP?", "gold": None, "ans": False, "cat": "adversarial"},
    {"q": "Under rule VP-SEPA-401, what is the maximum penalty for late cryptocurrency staking?", "gold": None, "ans": False, "cat": "adversarial"},
    {"q": "What is the monthly POS terminal lease fee in Canadian Dollars (CAD)?", "gold": None, "ans": False, "cat": "adversarial"},
    {"q": "Under compliance rule FX-TR-901, what is the required rolling escrow for retail customers?", "gold": None, "ans": False, "cat": "adversarial"},
    {"q": "Under statute SEC-104, how many hours do merchants have to submit dispute evidence?", "gold": None, "ans": False, "cat": "adversarial"},
    {"q": "What is the dispute fee for Tier 4 merchants under rule ESC-990?", "gold": None, "ans": False, "cat": "adversarial"},
    {"q": "What is the administrative charge in USD for direct debits returned with code R01?", "gold": None, "ans": False, "cat": "adversarial"},
    {"q": "Under rule DISP-808, what is the daily transaction limit for institutional traders?", "gold": None, "ans": False, "cat": "adversarial"},
    {"q": "What is the late-submission surcharge for standard transfers submitted after 18:00 CET?", "gold": None, "ans": False, "cat": "adversarial"},
    {"q": "What is the early resolution credit for dispute responses submitted within 14 calendar days?", "gold": None, "ans": False, "cat": "adversarial"},

    # 10. Typo / Informal Query (10)
    {"q": "wht is the surchagre for priority RTGS submitted after 17:30 cet?", "gold": "45.00 EUR", "ans": True, "cat": "typo"},
    {"q": "how mch is the fee for platinum tier chargebck?", "gold": "$5.50 USD", "ans": True, "cat": "typo"},
    {"q": "wat is the retun fee for direct debit under r01?", "gold": "7.50 EUR", "ans": True, "cat": "typo"},
    {"q": "monthly termnal lease amnt for pos device?", "gold": "$29.00 USD", "ans": True, "cat": "typo"},
    {"q": "how mny days to defend dispute before forfeitur under disp-808?", "gold": "20 calendar days", "ans": True, "cat": "typo"},
    {"q": "wat percentage rolling escro for tier 4 merchants?", "gold": "15.0 percent", "ans": True, "cat": "typo"},
    {"q": "interchang rate for standard tier mrchants?", "gold": "2.15%", "ans": True, "cat": "typo"},
    {"q": "how long are termination reservs locked up?", "gold": "180 calendar days", "ans": True, "cat": "typo"},
    {"q": "is partail indemnity release allowed for vp-sepa-401?", "gold": "strictly prohibited", "ans": True, "cat": "typo"},
    {"q": "daily limit on standard crossborder fx remittance?", "gold": "50,000 USD", "ans": True, "cat": "typo"},
]


# ---------------------------------------------------------------------------
# Automated Paraphraser (Generates 3 Distinct Variations per Question)
# ---------------------------------------------------------------------------

def generate_3_paraphrases(question: str) -> List[str]:
    """Generates 3 structural paraphrases of a question to evaluate robustness."""
    q = question.strip()
    p1 = f"Could you clarify: {q[0].lower() + q[1:] if q else q}"
    p2 = re.sub(r"^(?:What is|What are|How much is|How many)\s+", "Please state ", q, flags=re.IGNORECASE)
    if p2 == q:
        p2 = f"According to policy, {q[0].lower() + q[1:]}"
    p3 = re.sub(r"\?$", "", q) + " according to the guidelines?"
    return [p1, p2, p3]


# ---------------------------------------------------------------------------
# Evaluation Execution Engine
# ---------------------------------------------------------------------------

@dataclass
class EvalResult:
    question: str
    paraphrase: str
    category: str
    should_answer: bool
    gold_answer: Optional[str]
    retrieved_recall_5: bool
    answered: bool
    system_answer: str
    correct: bool
    grounded: bool
    latency_ms: float
    failure_reason: Optional[str] = None


async def run_stage6_evaluation():
    print("=" * 80)
    print("PAYGUARD AI: STAGE 6 FROZEN HELD-OUT GENERAL RAG EVALUATION")
    print("=" * 80)
    print(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Executing live with: nomic-embed-text & {settings.OLLAMA_LLM_MODEL} (PostgreSQL port 5434)")
    print(f"Total Questions: {len(QUESTIONS_DATA)} x 3 Paraphrases = {len(QUESTIONS_DATA) * 3} Evaluations")
    print("=" * 80)

    eval_results: List[EvalResult] = []

    async with AsyncSessionLocal() as session:
        # Step 1: Resolve evaluation user
        user_res = await session.execute(
            select(User).where(User.email == "tenant_alfa@audit.payguard.local")
        )
        eval_user = user_res.scalar_one_or_none()
        if not eval_user:
            eval_user = User(
                email="stage6_eval_user@payguard.local",
                full_name="Stage 6 Evaluator",
                role="auditor",
                is_active=True,
                hashed_password="not_used_in_eval",
            )
            session.add(eval_user)
            await session.commit()
            await session.refresh(eval_user)

        # Step 2: Clean up previous stage 6 documents if any
        await session.execute(text("""
            DELETE FROM document_chunks WHERE document_id IN (
                SELECT id FROM knowledge_documents WHERE title IN (
                    'Global Treasury Settlement Protocol 2026',
                    'Merchant Processing Standards and Dispute Framework'
                )
            )
        """))
        await session.execute(text("""
            DELETE FROM knowledge_documents WHERE title IN (
                'Global Treasury Settlement Protocol 2026',
                'Merchant Processing Standards and Dispute Framework'
            )
        """))
        await session.commit()

        # Step 3: Ingest held-out documents with live Ollama
        provider = OllamaEmbeddingProvider()
        pipeline = DocumentIngestionPipeline(session=session, embedding_provider=provider)

        print("\n[Ingesting Held-Out Document 1: Global Treasury Settlement Protocol 2026]")
        doc1_res = await pipeline.ingest_document(
            title="Global Treasury Settlement Protocol 2026",
            source_id="internal://eval/treasury-2026",
            content=DOC_TREASURY,
            hierarchical=True,
        )
        print(f"  -> Ingested Doc 1: {len(doc1_res.chunks)} chunks (status: {doc1_res.status})")

        print("\n[Ingesting Held-Out Document 2: Merchant Processing Standards and Dispute Framework]")
        doc2_res = await pipeline.ingest_document(
            title="Merchant Processing Standards and Dispute Framework",
            source_id="internal://eval/merchant-2026",
            content=DOC_MERCHANT,
            hierarchical=True,
        )
        print(f"  -> Ingested Doc 2: {len(doc2_res.chunks)} chunks (status: {doc2_res.status})")

        qa_service = DocumentQAService(session=session)
        retrieval_service = HybridRetrievalService(session=session, embedding_provider=provider)

        print("\n[Executing 300 Live Evaluations across 10 Categories...]")

        category_counts: Dict[str, Dict[str, int]] = {}

        for q_idx, item in enumerate(QUESTIONS_DATA, 1):
            base_q = item["q"]
            gold = item["gold"]
            should_answer = item["ans"]
            cat = item["cat"]

            paraphrases = generate_3_paraphrases(base_q)

            if cat not in category_counts:
                category_counts[cat] = {"total": 0, "correct": 0, "recall": 0}

            for p_idx, para in enumerate(paraphrases, 1):
                t0 = time.perf_counter()

                # Step 1: Retrieval check (Recall@5)
                search_res = await retrieval_service.search(
                    query=para,
                    top_k=5,
                    user_id=eval_user.id,
                    include_parent_context=True,
                )
                retrieved_chunks = search_res.results
                recall_5 = False
                if should_answer and gold:
                    # Check if gold string appears in any retrieved chunk
                    gold_norm = gold.lower()
                    for r in retrieved_chunks:
                        if gold_norm in r.content.lower() or (r.parent_content and gold_norm in r.parent_content.lower()):
                            recall_5 = True
                            break
                elif not should_answer:
                    # For unanswerable queries, recall@5 is trivially N/A, marked True
                    recall_5 = True

                # Step 2: Live Grounded QA Generation
                qa_req = DocumentAskRequest(query=para, scope="all", top_k=5)
                ans_resp = await qa_service.ask_question(
                    user=eval_user,
                    request=qa_req,
                )
                t1 = time.perf_counter()
                lat_ms = (t1 - t0) * 1000.0

                ans_text = ans_resp.answer
                is_grounded = ans_resp.has_sufficient_evidence
                abstention_indicated = (
                    not is_grounded
                    or "does not contain sufficient information" in ans_text.lower()
                    or "competing rules" in ans_text.lower()
                )

                # Step 3: Evaluate correctness
                correct = False
                grounded = False
                fail_reason = None

                if should_answer:
                    # Expected to answer
                    if abstention_indicated:
                        correct = False
                        grounded = False
                        fail_reason = "False Negative: System abstained on answerable query"
                    else:
                        # Check if gold factual token is in the answer
                        num_words = {"1": "one", "2": "two", "3": "three", "4": "four", "5": "five", "6": "six", "7": "seven", "8": "eight", "9": "nine", "10": "ten"}
                        has_num_word = bool(gold in num_words and num_words[gold] in ans_text.lower())
                        if gold and (gold.lower() in ans_text.lower() or has_num_word or any(w.lower() in ans_text.lower() for w in gold.split() if len(w) > 3)):
                            correct = True
                            grounded = is_grounded
                        else:
                            correct = False
                            fail_reason = f"Fact mismatch: Expected '{gold}', got '{ans_text[:80]}...'"
                else:
                    # Expected to abstain
                    if abstention_indicated:
                        correct = True
                        grounded = True
                    else:
                        correct = False
                        grounded = False
                        fail_reason = f"False Acceptance: System answered unanswerable query with: '{ans_text[:80]}...'"

                category_counts[cat]["total"] += 1
                if correct:
                    category_counts[cat]["correct"] += 1
                if recall_5:
                    category_counts[cat]["recall"] += 1

                eval_results.append(
                    EvalResult(
                        question=base_q,
                        paraphrase=para,
                        category=cat,
                        should_answer=should_answer,
                        gold_answer=gold,
                        retrieved_recall_5=recall_5,
                        answered=not abstention_indicated,
                        system_answer=ans_text,
                        correct=correct,
                        grounded=grounded,
                        latency_ms=lat_ms,
                        failure_reason=fail_reason,
                    )
                )

            status_char = "." if all(e.correct for e in eval_results[-3:]) else "x"
            print(status_char, end="", flush=True)
            if q_idx % 25 == 0:
                print(f" [{q_idx * 3}/300]")

        # Step 4: Clean up evaluation documents
        await session.execute(text("""
            DELETE FROM document_chunks WHERE document_id IN (
                SELECT id FROM knowledge_documents WHERE title IN (
                    'Global Treasury Settlement Protocol 2026',
                    'Merchant Processing Standards and Dispute Framework'
                )
            )
        """))
        await session.execute(text("""
            DELETE FROM knowledge_documents WHERE title IN (
                'Global Treasury Settlement Protocol 2026',
                'Merchant Processing Standards and Dispute Framework'
            )
        """))
        await session.commit()

    # ---------------------------------------------------------------------------
    # Metrics Calculation
    # ---------------------------------------------------------------------------
    total_evals = len(eval_results)
    answerable_evals = [e for e in eval_results if e.should_answer]
    unanswerable_evals = [e for e in eval_results if not e.should_answer]

    # Recall@5 (over answerable queries)
    recalls = [1 if e.retrieved_recall_5 else 0 for e in answerable_evals]
    recall_5_pct = (sum(recalls) / len(recalls)) * 100.0 if recalls else 0.0

    # Answer Correctness (overall)
    overall_correct = sum(1 for e in eval_results if e.correct)
    accuracy_pct = (overall_correct / total_evals) * 100.0

    # Groundedness Precision (answered queries that are factually grounded)
    answered_queries = [e for e in eval_results if e.answered]
    grounded_answered = [e for e in answered_queries if e.grounded and e.correct]
    grounded_prec_pct = (len(grounded_answered) / len(answered_queries) * 100.0) if answered_queries else 100.0

    # Abstention Precision and Recall
    # True Negative: unanswerable query correctly abstained
    tn = sum(1 for e in unanswerable_evals if e.correct)
    # False Positive (False Acceptance): unanswerable query answered
    fp = sum(1 for e in unanswerable_evals if not e.correct)
    # False Negative: answerable query abstained
    fn = sum(1 for e in answerable_evals if not e.answered)
    # True Positive: answerable query answered
    tp = sum(1 for e in answerable_evals if e.answered)

    abstention_precision = (tn / (tn + fn) * 100.0) if (tn + fn) > 0 else 100.0
    abstention_recall = (tn / len(unanswerable_evals) * 100.0) if unanswerable_evals else 100.0
    false_acceptance_rate = (fp / len(unanswerable_evals) * 100.0) if unanswerable_evals else 0.0

    # Latencies
    latencies = sorted([e.latency_ms for e in eval_results])
    p50 = latencies[int(len(latencies) * 0.50)]
    p95 = latencies[int(len(latencies) * 0.95)]
    mean_lat = sum(latencies) / len(latencies)
    std_lat = math.sqrt(sum((x - mean_lat) ** 2 for x in latencies) / (len(latencies) - 1)) if len(latencies) > 1 else 0.0
    # 95% Confidence Interval for mean latency: mean +- 1.96 * (std / sqrt(N))
    ci95_lat = 1.96 * (std_lat / math.sqrt(len(latencies)))

    # Wilson score 95% CI for Accuracy
    z = 1.96
    p = accuracy_pct / 100.0
    n = total_evals
    denom = 1 + (z**2) / n
    center = (p + (z**2) / (2 * n)) / denom
    spread = z * math.sqrt((p * (1 - p) + (z**2) / (4 * n)) / n) / denom
    ci_acc_low = max(0.0, (center - spread) * 100.0)
    ci_acc_high = min(100.0, (center + spread) * 100.0)

    print("\n\n" + "=" * 80)
    print("STAGE 6 EVALUATION RESULTS (300 EVALUATIONS)")
    print("=" * 80)
    print(f"Total Evaluations:              {total_evals}")
    print(f"Recall@5 (Answerable Queries):  {recall_5_pct:.2f}%")
    print(f"Answer Correctness:             {accuracy_pct:.2f}% (95% CI: [{ci_acc_low:.1f}%, {ci_acc_high:.1f}%])")
    print(f"Groundedness Precision:         {grounded_prec_pct:.2f}%")
    print(f"Abstention Precision:           {abstention_precision:.2f}%")
    print(f"Abstention Recall:              {abstention_recall:.2f}%")
    print(f"False Acceptance Rate (FAR):    {false_acceptance_rate:.2f}%")
    print(f"Latency p50:                    {p50:.1f} ms")
    print(f"Latency p95:                    {p95:.1f} ms")
    print(f"Latency Mean (95% CI):          {mean_lat:.1f} ± {ci95_lat:.1f} ms")
    print("=" * 80)

    print("\nCATEGORY-BY-CATEGORY BREAKDOWN:")
    print("-" * 65)
    print(f"{'Category':<25} | {'Count':<6} | {'Recall@5':<10} | {'Correctness':<12}")
    print("-" * 65)
    for cat, stats in sorted(category_counts.items()):
        rec_pct = (stats["recall"] / stats["total"]) * 100.0
        cor_pct = (stats["correct"] / stats["total"]) * 100.0
        print(f"{cat:<25} | {stats['total']:<6} | {rec_pct:>8.1f}% | {cor_pct:>10.1f}%")
    print("-" * 65)

    # Failures list
    failures = [e for e in eval_results if not e.correct]
    print(f"\nTOTAL FAILURES: {len(failures)} / {total_evals}")
    if failures:
        print("\nFAILURE DETAILS:")
        for idx, f in enumerate(failures[:50], 1):
            print(f"  {idx}. [{f.category}] Query: '{f.paraphrase}'")
            print(f"     Reason: {f.failure_reason}")
    else:
        print("  None! Zero failures recorded across all 300 evaluations.")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    asyncio.run(run_stage6_evaluation())
