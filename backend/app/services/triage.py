"""Deterministic Triage Rules Engine for PayGuard AI.

Implements rule-based, non-hallucinating classification based on gateway error codes,
transaction lifecycles, and keyword heuristics.
"""

import re
from typing import Optional

from backend.app.schemas.payment import PaymentDetailResponse
from backend.app.services.interfaces import (
    ITriageEngine,
    TriageClassificationResult,
)


class TriageRulesEngine(ITriageEngine):
    """Deterministic payment triage engine.
    Matches failure codes, lifecycle statuses, and query intents.
    """

    DUPLICATE_KEYWORDS = re.compile(r"\b(duplicate|twice|double charged|charged two times|multiple times)\b", re.IGNORECASE)
    REFUND_KEYWORDS = re.compile(r"\b(refund|credit not received|return money|money back|dispute|chargeback)\b", re.IGNORECASE)
    PENDING_KEYWORDS = re.compile(r"\b(pending|delayed|holding|still waiting|in review|processing)\b", re.IGNORECASE)
    FAILED_KEYWORDS = re.compile(r"\b(declined|failed|rejected|error|insufficient|cancelled)\b", re.IGNORECASE)

    def classify_payment_issue(
        self,
        payment: Optional[PaymentDetailResponse],
        user_query: str,
    ) -> TriageClassificationResult:
        query_text = user_query.strip()
        missing_fields = []

        if not payment:
            missing_fields.append("payment_record")

        # 1. Rule: Check Payment Status if record exists
        if payment:
            if payment.status == "failed":
                return TriageClassificationResult(
                    category="failed_payment",
                    confidence_score=0.98,
                    rule_id_matched="RULE_PAYMENT_STATUS_FAILED",
                    identified_failure_code=payment.failure_code,
                    is_ambiguous=False,
                    missing_fields=missing_fields,
                )
            if payment.status in ("pending", "authorized"):
                # If authorized hold is questioned
                if self.DUPLICATE_KEYWORDS.search(query_text):
                    return TriageClassificationResult(
                        category="duplicate_charge",
                        confidence_score=0.92,
                        rule_id_matched="RULE_PENDING_DUPLICATE_INQUIRY",
                        identified_failure_code=payment.failure_code,
                        is_ambiguous=False,
                        missing_fields=missing_fields,
                    )
                return TriageClassificationResult(
                    category="pending_payment",
                    confidence_score=0.95,
                    rule_id_matched="RULE_PAYMENT_STATUS_PENDING",
                    identified_failure_code=payment.failure_code,
                    is_ambiguous=False,
                    missing_fields=missing_fields,
                )
            if payment.status in ("refunded", "partially_refunded", "disputed"):
                return TriageClassificationResult(
                    category="refund_status",
                    confidence_score=0.96,
                    rule_id_matched="RULE_PAYMENT_STATUS_REFUNDED",
                    identified_failure_code=payment.failure_code,
                    is_ambiguous=False,
                    missing_fields=missing_fields,
                )

        # 2. Rule: Query Regex Signals (when payment is missing or status is captured)
        if self.DUPLICATE_KEYWORDS.search(query_text):
            return TriageClassificationResult(
                category="duplicate_charge",
                confidence_score=0.90,
                rule_id_matched="RULE_QUERY_KEYWORD_DUPLICATE",
                is_ambiguous=False,
                missing_fields=missing_fields,
            )

        if self.REFUND_KEYWORDS.search(query_text):
            return TriageClassificationResult(
                category="refund_status",
                confidence_score=0.88,
                rule_id_matched="RULE_QUERY_KEYWORD_REFUND",
                is_ambiguous=False,
                missing_fields=missing_fields,
            )

        if self.FAILED_KEYWORDS.search(query_text):
            return TriageClassificationResult(
                category="failed_payment",
                confidence_score=0.85,
                rule_id_matched="RULE_QUERY_KEYWORD_FAILED",
                is_ambiguous=False,
                missing_fields=missing_fields,
            )

        if self.PENDING_KEYWORDS.search(query_text):
            return TriageClassificationResult(
                category="pending_payment",
                confidence_score=0.85,
                rule_id_matched="RULE_QUERY_KEYWORD_PENDING",
                is_ambiguous=False,
                missing_fields=missing_fields,
            )

        # 3. Default fallback for ambiguous or unclassified queries
        return TriageClassificationResult(
            category="unknown_or_other",
            confidence_score=0.50,
            rule_id_matched="RULE_FALLBACK_UNKNOWN",
            is_ambiguous=True,
            missing_fields=missing_fields,
        )
