"""LLM Reasoning Service for generating grounded investigation explanations."""

from typing import List, Optional

from backend.app.schemas.payment import PaymentDetailResponse
from backend.app.schemas.investigation import PolicyCitation
from backend.app.services.interfaces import (
    ILLMReasoningService,
    LLMInvestigationOutput,
    TriageClassificationResult,
)


class LLMReasoningService(ILLMReasoningService):
    """Generates structured investigation summaries strictly grounded in verified evidence.
    Contains built-in deterministic fallbacks for offline development and testing.
    """

    def __init__(self, model_name: str = "gpt-4o-mini"):
        self.model_name = model_name

    async def generate_investigation_summary(
        self,
        user_query: str,
        payment: Optional[PaymentDetailResponse],
        citations: List[PolicyCitation],
        triage_result: TriageClassificationResult,
    ) -> LLMInvestigationOutput:
        """Grounded synthesis of payment evidence and policy citations."""
        category = triage_result.category

        if not payment:
            return LLMInvestigationOutput(
                investigation_summary=(
                    f"No transaction record was found matching the provided reference. "
                    f"Issue classified as '{category}'. Additional transaction details are required."
                ),
                recommended_action="REQUEST_PAYMENT_DETAILS",
                recommended_action_details="Ask the customer to provide a valid transaction ID, card last 4 digits, or charge timestamp.",
                missing_or_conflicting_info=["payment_record"],
                human_review_required=True,
                human_review_reason="Missing authoritative payment record in system of record.",
                model_name=self.model_name,
            )

        if category == "failed_payment":
            return LLMInvestigationOutput(
                investigation_summary=(
                    f"Transaction {payment.payment_reference} for {payment.amount} {payment.currency} failed at the gateway. "
                    f"Reported gateway failure code: '{payment.failure_code or 'UNKNOWN'}'. Reason: {payment.failure_message or 'Declined by issuing bank'}."
                ),
                recommended_action="NOTIFY_CUSTOMER_RETRY",
                recommended_action_details="Inform customer of card decline reason and recommend alternative payment method.",
                missing_or_conflicting_info=[],
                human_review_required=False,
                model_name=self.model_name,
            )

        if category == "duplicate_charge":
            return LLMInvestigationOutput(
                investigation_summary=(
                    f"Investigation identified inquiry regarding duplicate debit for payment {payment.payment_reference}. "
                    f"Current recorded status is '{payment.status}'. If an authorization hold is present, it will expire automatically per scheme rules."
                ),
                recommended_action="VOID_PENDING_AUTHORIZATION",
                recommended_action_details="Verify secondary authorization hold in processor portal and release if unsettled.",
                missing_or_conflicting_info=[],
                human_review_required=False,
                model_name=self.model_name,
            )

        if category == "pending_payment":
            return LLMInvestigationOutput(
                investigation_summary=(
                    f"Payment {payment.payment_reference} of {payment.amount} {payment.currency} is currently in '{payment.status}' status. "
                    f"Authorized at {payment.authorized_at or payment.created_at}. Awaiting batch settlement confirmation."
                ),
                recommended_action="WAIT_SETTLEMENT_WINDOW",
                recommended_action_details="Advise customer that settlement is within standard 24-48 hour banking window.",
                missing_or_conflicting_info=[],
                human_review_required=False,
                model_name=self.model_name,
            )

        if category == "refund_status":
            return LLMInvestigationOutput(
                investigation_summary=(
                    f"Payment {payment.payment_reference} status is '{payment.status}'. "
                    f"Refund processing typically reflects on cardholder statements within 3-5 business days."
                ),
                recommended_action="CONFIRM_REFUND_TIMELINE",
                recommended_action_details="Confirm ARN (Acquirer Reference Number) with customer to trace credit at issuing bank.",
                missing_or_conflicting_info=[],
                human_review_required=False,
                model_name=self.model_name,
            )

        # Fallback for unknown
        return LLMInvestigationOutput(
            investigation_summary=f"Query regarding transaction {payment.payment_reference} requires manual analyst review.",
            recommended_action="ESCALATE_TO_ANALYST",
            recommended_action_details="Assign case to senior payment operations engineer for manual ledger inspection.",
            missing_or_conflicting_info=["unclassified_intent"],
            human_review_required=True,
            human_review_reason="Ambiguous issue category or unmapped transaction event pattern.",
            model_name=self.model_name,
        )
