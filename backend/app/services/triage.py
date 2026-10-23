"""Deterministic Triage Rules Engine for PayGuard AI.

Implements rule-based, non-hallucinating classification based on gateway error codes,
transaction lifecycles, event chronologies, and keyword heuristics.

Guarantees:
- A gateway timeout does not prove a payment failed.
- A pending payment is not automatically deemed successful or failed.
- A refund request does not prove that a refund was completed.
- An authorization hold is not necessarily a captured payment.
- Duplicate-charge suspicion is not proof of two completed charges.
- When records or events conflict, reports conflict explicitly and flags human review.
- When evidence is insufficient, states exactly what is missing.
- Every classification includes supporting record or event identifiers when available.
"""

import re
from typing import List, Optional

from backend.app.schemas.payment import PaymentDetailResponse
from backend.app.services.interfaces import (
    ITriageEngine,
    TriageClassificationResult,
)


class TriageRulesEngine(ITriageEngine):
    """Deterministic payment triage engine.
    Matches failure codes, lifecycle statuses, event chronologies, and query intents.
    """

    DUPLICATE_KEYWORDS = re.compile(
        r"\b(duplicate|twice|double charged|charged two times|multiple times|second charge)\b",
        re.IGNORECASE,
    )
    REFUND_KEYWORDS = re.compile(
        r"\b(refund|credit not received|return money|money back|dispute|chargeback|reversal)\b",
        re.IGNORECASE,
    )
    PENDING_KEYWORDS = re.compile(
        r"\b(pending|delayed|holding|still waiting|in review|processing|settlement)\b",
        re.IGNORECASE,
    )
    FAILED_KEYWORDS = re.compile(
        r"\b(declined|failed|rejected|error|insufficient|cancelled|do not honor|blocked)\b",
        re.IGNORECASE,
    )
    TIMEOUT_KEYWORDS = re.compile(
        r"\b(timeout|timed out|gateway timeout|504|upstream timeout|no response|gateway error)\b",
        re.IGNORECASE,
    )
    HOLD_KEYWORDS = re.compile(
        r"\b(hold|authorization hold|pre-auth|preauth|reserved funds|pending hold)\b",
        re.IGNORECASE,
    )

    def classify_payment_issue(
        self,
        payment: Optional[PaymentDetailResponse],
        user_query: str,
    ) -> TriageClassificationResult:
        query_text = user_query.strip()
        missing_fields: List[str] = []
        conflicts: List[str] = []
        supporting_record_ids: List[str] = []

        # Case A: Missing Payment Record
        if not payment:
            missing_fields.append("payment_record")
            if self.DUPLICATE_KEYWORDS.search(query_text):
                return TriageClassificationResult(
                    category="duplicate_charge",
                    confidence_score=0.90,
                    rule_id_matched="RULE_QUERY_KEYWORD_DUPLICATE",
                    is_ambiguous=False,
                    missing_fields=missing_fields,
                    recommended_action="REQUEST_PAYMENT_DETAILS",
                    recommended_action_details="Request customer provide payment reference, merchant, and transaction timestamp to trace duplicate.",
                    supporting_record_ids=[],
                )
            if self.REFUND_KEYWORDS.search(query_text):
                return TriageClassificationResult(
                    category="refund_status",
                    confidence_score=0.88,
                    rule_id_matched="RULE_QUERY_KEYWORD_REFUND",
                    is_ambiguous=False,
                    missing_fields=missing_fields,
                    recommended_action="REQUEST_PAYMENT_DETAILS",
                    recommended_action_details="Request original transaction ID or refund reference number to trace refund status.",
                    supporting_record_ids=[],
                )
            if self.FAILED_KEYWORDS.search(query_text):
                return TriageClassificationResult(
                    category="failed_payment",
                    confidence_score=0.85,
                    rule_id_matched="RULE_QUERY_KEYWORD_FAILED",
                    is_ambiguous=False,
                    missing_fields=missing_fields,
                    recommended_action="REQUEST_PAYMENT_DETAILS",
                    recommended_action_details="Request transaction reference or customer identifier to investigate decline reason.",
                    supporting_record_ids=[],
                )

            return TriageClassificationResult(
                category="unknown_or_other",
                confidence_score=0.45,
                rule_id_matched="RULE_MISSING_PAYMENT_RECORD",
                is_ambiguous=True,
                missing_fields=missing_fields,
                recommended_action="REQUEST_PAYMENT_DETAILS",
                recommended_action_details="Payment identifier or reference not found in payment system of record. Ask customer for transaction receipt.",
                supporting_record_ids=[],
            )

        # Payment record is present
        supporting_record_ids.append(str(payment.id))
        for evt in payment.events:
            supporting_record_ids.append(str(evt.id))

        # Check if events list is empty
        if not payment.events:
            missing_fields.append("payment_event_history")

        # Case B: Contradictory Payment Events
        # e.g., payment has both a failed event and a captured/settled event
        events_statuses = [e.to_status for e in payment.events]
        has_failed_event = any(s == "failed" for s in events_statuses)
        has_captured_event = any(s in ("captured", "settled") for s in events_statuses)
        if has_failed_event and has_captured_event:
            conflicts.append("Contradictory events in timeline: both 'failed' and 'captured' states recorded.")
            return TriageClassificationResult(
                category="failed_payment" if payment.status == "failed" else "unknown_or_other",
                confidence_score=0.85,
                rule_id_matched="RULE_CONTRADICTORY_PAYMENT_EVENTS",
                identified_failure_code=payment.failure_code,
                is_ambiguous=True,
                missing_fields=missing_fields,
                conflicting_evidence=conflicts,
                supporting_record_ids=supporting_record_ids,
                recommended_action="ESCALATE_TO_ANALYST",
                recommended_action_details="Contradictory state transitions detected in event ledger. Escalate to senior payment engineer to inspect gateway settlement report.",
            )

        # Case C: Gateway Timeout with Unknown Final Outcome
        # Gateway timeout does NOT prove failure; processor status is indeterminate
        is_timeout_failure = payment.failure_code and any(
            t in payment.failure_code.upper() for t in ("TIMEOUT", "504", "TIMED_OUT")
        )
        has_timeout_event = any(
            "timeout" in e.event_type.lower() or "504" in str(e.raw_payload)
            for e in payment.events
        )
        query_mentions_timeout = bool(self.TIMEOUT_KEYWORDS.search(query_text))

        if (is_timeout_failure or has_timeout_event or (payment.status == "pending" and query_mentions_timeout)) and not has_captured_event:
            conflicts.append("Gateway timeout occurred: payment outcome at processor is unconfirmed without reconciliation query.")
            return TriageClassificationResult(
                category="pending_payment" if payment.status == "pending" else "failed_payment",
                confidence_score=0.88,
                rule_id_matched="RULE_GATEWAY_TIMEOUT_UNKNOWN_OUTCOME",
                identified_failure_code=payment.failure_code or "GATEWAY_TIMEOUT_504",
                is_ambiguous=True,
                missing_fields=["gateway_reconciliation_status"],
                conflicting_evidence=conflicts,
                supporting_record_ids=supporting_record_ids,
                recommended_action="QUERY_GATEWAY_STATUS",
                recommended_action_details="Do NOT instruct customer to retry immediately. Query gateway GET /charges endpoint with idempotency key to prevent double debit.",
            )

        # Case D: Duplicate Charge Suspicion
        # Duplicate inquiry does not prove two completed charges
        if self.DUPLICATE_KEYWORDS.search(query_text):
            return TriageClassificationResult(
                category="duplicate_charge",
                confidence_score=0.92,
                rule_id_matched="RULE_DUPLICATE_CHARGE_SUSPICION",
                identified_failure_code=payment.failure_code,
                is_ambiguous=False,
                missing_fields=missing_fields,
                supporting_record_ids=supporting_record_ids,
                recommended_action="INSPECT_DUPLICATE_CHARGES",
                recommended_action_details="Search customer billing records for secondary charges within 30 minutes. If secondary record is an uncaptured authorization hold, release hold.",
            )

        # Case E: Authorization Hold Without Confirmed Capture
        # An authorization hold is not a captured payment
        if payment.status in ("authorized", "pending") and (payment.authorized_at is not None or self.HOLD_KEYWORDS.search(query_text)):
            if payment.captured_at is None and not has_captured_event:
                return TriageClassificationResult(
                    category="pending_payment",
                    confidence_score=0.94,
                    rule_id_matched="RULE_AUTHORIZATION_HOLD_UNCAPTURED",
                    identified_failure_code=payment.failure_code,
                    is_ambiguous=False,
                    missing_fields=missing_fields,
                    supporting_record_ids=supporting_record_ids,
                    recommended_action="EXPLAIN_AUTHORIZATION_HOLD",
                    recommended_action_details="Explain that funds are currently on authorization hold, not settled. Uncaptured authorizations drop automatically in 1-7 business days per card scheme.",
                )

        # Case F: Refund Requested / Refund Processing
        # A refund request does not prove refund was completed
        if payment.status in ("refunded", "partially_refunded", "disputed") or self.REFUND_KEYWORDS.search(query_text):
            is_confirmed = payment.status in ("refunded", "partially_refunded")
            return TriageClassificationResult(
                category="refund_status",
                confidence_score=0.96 if is_confirmed else 0.90,
                rule_id_matched="RULE_PAYMENT_STATUS_REFUNDED" if is_confirmed else "RULE_REFUND_REQUESTED_UNCONFIRMED",
                identified_failure_code=payment.failure_code,
                is_ambiguous=not is_confirmed,
                missing_fields=["acquirer_reference_number"] if not is_confirmed else [],
                supporting_record_ids=supporting_record_ids,
                recommended_action="CONFIRM_REFUND_TIMELINE" if is_confirmed else "VERIFY_REFUND_PIPELINE",
                recommended_action_details=(
                    "Confirm ARN (Acquirer Reference Number) with customer; refunds take 3-5 business days to post to bank."
                    if is_confirmed
                    else "Verify refund submission in gateway ledger. Check if payment processor cutoff has occurred."
                ),
            )

        # Case G: Failed / Declined Payment
        if payment.status == "failed":
            return TriageClassificationResult(
                category="failed_payment",
                confidence_score=0.98,
                rule_id_matched="RULE_PAYMENT_STATUS_FAILED",
                identified_failure_code=payment.failure_code,
                is_ambiguous=False,
                missing_fields=missing_fields,
                supporting_record_ids=supporting_record_ids,
                recommended_action="NOTIFY_CUSTOMER_RETRY",
                recommended_action_details=f"Inform customer of decline reason ({payment.failure_code or 'card_declined'}) and suggest alternate payment method.",
            )

        # Case H: Pending Payment (Standard)
        if payment.status in ("pending", "processing"):
            return TriageClassificationResult(
                category="pending_payment",
                confidence_score=0.95,
                rule_id_matched="RULE_PAYMENT_STATUS_PENDING",
                identified_failure_code=payment.failure_code,
                is_ambiguous=False,
                missing_fields=missing_fields,
                supporting_record_ids=supporting_record_ids,
                recommended_action="WAIT_SETTLEMENT_WINDOW",
                recommended_action_details="Advise customer that payment is currently processing within the standard 24-48 hour banking settlement window.",
            )

        # Case I: Completed / Captured Payment with General Query
        if payment.status in ("captured", "settled"):
            return TriageClassificationResult(
                category="unknown_or_other",
                confidence_score=0.95,
                rule_id_matched="RULE_PAYMENT_CAPTURED_SUCCESS",
                is_ambiguous=False,
                missing_fields=missing_fields,
                supporting_record_ids=supporting_record_ids,
                recommended_action="CONFIRM_PAYMENT_COMPLETED",
                recommended_action_details=f"Transaction {payment.payment_reference} is successfully captured and settled. No payment failure detected.",
            )

        # Case J: Fallback for Insufficient Evidence / Ambiguous
        return TriageClassificationResult(
            category="unknown_or_other",
            confidence_score=0.50,
            rule_id_matched="RULE_INSUFFICIENT_EVIDENCE",
            is_ambiguous=True,
            missing_fields=["detailed_issue_description"],
            supporting_record_ids=supporting_record_ids,
            recommended_action="ESCALATE_TO_ANALYST",
            recommended_action_details="Query is ambiguous or lacks sufficient evidence to reach a deterministic triage conclusion.",
        )
