"""Targeted regression tests for RAG evidence scoring, specificity, and ambiguity handling.

Covers:
- HT01: Legitimate dispute/contest paraphrasing without semantic leakage
- HT01 Negatives: Legally distinct terms (arbitration vs dispute, loans vs fees) must abstain
- HT05: Specific rule exception vs general section rules (VP-SEPA-401 partial release)
- Standard vs Expedited modifier pairs
- Domestic vs International modifier pairs
- Currency constraint enforcement and absent currency abstention
- Conflicting competing rules in the same section without distinguishing query criteria (must abstain)
- Exact alphanumeric rule identifier discrimination (GS-7712 vs GS-9920)
"""

import pytest
from backend.app.services.document_qa import DocumentQAService, CitedExcerptItem


@pytest.fixture
def qa_service() -> DocumentQAService:
    return DocumentQAService(session=None)


@pytest.mark.asyncio
async def test_ht01_paraphrase_positive_match(qa_service: DocumentQAService):
    """HT01: High-tier dispute paraphrase matches Platinum fee assessment sentence."""
    query = "How much is billed to a top-tier seller when a customer contests a card transaction?"
    excerpt = CitedExcerptItem(
        document_id="22222222-2222-2222-2222-222222222222",
        document_title="Merchant Fee Schedule",
        section_title="Dispute and Chargeback Fees",
        page_number=3,
        score=0.95,
        excerpt=(
            "Standard dispute fee is $15.00 USD per occurrence. "
            "For Platinum tier merchants, the dispute assessment is reduced to $8.25 USD. "
            "Enterprise volume merchants processing over 10,000,000 USD monthly pay $5.00 USD."
        ),
    )

    ans, is_grounded, best_item = await qa_service._synthesize_grounded_answer(query, [excerpt])
    assert is_grounded is True
    assert "$8.25 USD" in ans or "8.25" in ans
    assert "Platinum tier" in ans


@pytest.mark.asyncio
async def test_ht01_paraphrase_negative_arbitration_must_abstain(qa_service: DocumentQAService):
    """HT01 Negative: Query asks about arbitration hearing, which is legally distinct from dispute."""
    query = "How much is billed to a top-tier seller when an arbitration hearing is initiated?"
    excerpt = CitedExcerptItem(
        document_id="22222222-2222-2222-2222-222222222222",
        document_title="Merchant Fee Schedule",
        section_title="Dispute and Chargeback Fees",
        page_number=3,
        score=0.95,
        excerpt=(
            "Standard dispute fee is $15.00 USD per occurrence. "
            "For Platinum tier merchants, the dispute assessment is reduced to $8.25 USD. "
            "Enterprise volume merchants processing over 10,000,000 USD monthly pay $5.00 USD."
        ),
    )

    ans, is_grounded, best_item = await qa_service._synthesize_grounded_answer(query, [excerpt])
    assert is_grounded is False
    assert "does not contain sufficient information" in ans


@pytest.mark.asyncio
async def test_ht01_paraphrase_negative_unrelated_loan_must_abstain(qa_service: DocumentQAService):
    """HT01 Negative: Distinct financial concept (loan interest) must not match fee schedule."""
    query = "What is the monthly interest rate charged to top-tier sellers for liquidity loans?"
    excerpt = CitedExcerptItem(
        document_id="22222222-2222-2222-2222-222222222222",
        document_title="Merchant Fee Schedule",
        section_title="Dispute and Chargeback Fees",
        page_number=3,
        score=0.95,
        excerpt=(
            "Standard dispute fee is $15.00 USD per occurrence. "
            "For Platinum tier merchants, the dispute assessment is reduced to $8.25 USD. "
            "Enterprise volume merchants processing over 10,000,000 USD monthly pay $5.00 USD."
        ),
    )

    ans, is_grounded, best_item = await qa_service._synthesize_grounded_answer(query, [excerpt])
    assert is_grounded is False
    assert "does not contain sufficient information" in ans


@pytest.mark.asyncio
async def test_ht05_specific_exception_outranks_general_rule(qa_service: DocumentQAService):
    """HT05: Specific partial indemnity rule VP-SEPA-401 outranks adjacent general full indemnity rule."""
    query = "Can a merchant obtain a partial indemnity release under rule VP-SEPA-401?"
    excerpt = CitedExcerptItem(
        document_id="33333333-3333-3333-3333-333333333333",
        document_title="SEPA Core Settlement & Indemnity Framework",
        section_title="Section 4.2 - Indemnity Obligations and Dispute Guarantees",
        page_number=12,
        score=0.95,
        excerpt=(
            "The full indemnity guarantee remains irrevocably in force across SEPA Core payment schemes, "
            "and standard indemnity release rules do not grant waiver of liability without formal counterparty consent. "
            "Partial indemnity release is prohibited under rule VP-SEPA-401, requiring complete restitution before any subsequent claim closure. "
            "Under SEPA direct debit B2B scheme regulations, refund requests for unauthorized transactions must be filed within 13 calendar days of the debit date."
        ),
    )

    ans, is_grounded, best_item = await qa_service._synthesize_grounded_answer(query, [excerpt])
    assert is_grounded is True
    assert "Partial indemnity release is prohibited under rule VP-SEPA-401" in ans
    assert "full indemnity guarantee remains irrevocably in force" not in ans


@pytest.mark.asyncio
async def test_standard_vs_expedited_fees_discrimination(qa_service: DocumentQAService):
    """Verify that sentence scoring distinguishes standard and expedited fees."""
    excerpt = CitedExcerptItem(
        document_id="44444444-4444-4444-4444-444444444444",
        document_title="ACH Processing Guide",
        section_title="Reversal Surcharges",
        page_number=2,
        score=0.92,
        excerpt=(
            "Standard ACH reversal surcharge is $4.50 USD per batch submission. "
            "Expedited same-day ACH reversal surcharge is $22.00 USD per batch submission."
        ),
    )

    # Standard query
    ans_std, g_std, _ = await qa_service._synthesize_grounded_answer(
        "What is the standard ACH reversal surcharge?", [excerpt]
    )
    assert g_std is True
    assert "$4.50 USD" in ans_std
    assert "$22.00 USD" not in ans_std

    # Expedited query
    ans_exp, g_exp, _ = await qa_service._synthesize_grounded_answer(
        "What is the expedited ACH reversal surcharge?", [excerpt]
    )
    assert g_exp is True
    assert "$22.00 USD" in ans_exp
    assert "$4.50 USD" not in ans_exp


@pytest.mark.asyncio
async def test_domestic_vs_international_transfers(qa_service: DocumentQAService):
    """Verify that sentence scoring discriminates domestic and international transfer terms."""
    excerpt = CitedExcerptItem(
        document_id="55555555-5555-5555-5555-555555555555",
        document_title="Treasury Transfer Handbook",
        section_title="Settlement Windows",
        page_number=5,
        score=0.90,
        excerpt=(
            "Domestic treasury transfers settle within 1 business day under local clearing rules. "
            "International treasury transfers settle within 4 business days subject to correspondent bank clearing."
        ),
    )

    # Domestic query
    ans_dom, g_dom, _ = await qa_service._synthesize_grounded_answer(
        "What is the settlement window for domestic treasury transfers?", [excerpt]
    )
    assert g_dom is True
    assert "1 business day" in ans_dom
    assert "4 business days" not in ans_dom

    # International query
    ans_intl, g_intl, _ = await qa_service._synthesize_grounded_answer(
        "What is the settlement window for international treasury transfers?", [excerpt]
    )
    assert g_intl is True
    assert "4 business days" in ans_intl
    assert "1 business day" not in ans_intl


@pytest.mark.asyncio
async def test_currency_discrimination_and_abstention(qa_service: DocumentQAService):
    """Verify that currency queries select matching currency rules and abstain on absent currencies."""
    excerpt = CitedExcerptItem(
        document_id="66666666-6666-6666-6666-666666666666",
        document_title="Foreign Exchange Clearing Protocols",
        section_title="Cross-Border Wire Levies",
        page_number=7,
        score=0.91,
        excerpt=(
            "Cross-border wire transfers denominated in EUR incur a 12.00 EUR clearing surcharge. "
            "Cross-border wire transfers denominated in USD incur a 15.00 USD clearing surcharge."
        ),
    )

    # EUR query
    ans_eur, g_eur, _ = await qa_service._synthesize_grounded_answer(
        "What is the cross-border wire clearing surcharge for EUR transfers?", [excerpt]
    )
    assert g_eur is True
    assert "12.00 EUR" in ans_eur

    # USD query
    ans_usd, g_usd, _ = await qa_service._synthesize_grounded_answer(
        "What is the cross-border wire clearing surcharge for USD transfers?", [excerpt]
    )
    assert g_usd is True
    assert "15.00 USD" in ans_usd

    # GBP query (absent currency) -> MUST ABSTAIN
    ans_gbp, g_gbp, _ = await qa_service._synthesize_grounded_answer(
        "What is the cross-border wire clearing surcharge for GBP transfers?", [excerpt]
    )
    assert g_gbp is False
    assert "does not contain sufficient information" in ans_gbp


@pytest.mark.asyncio
async def test_competing_rules_in_same_section_abstention(qa_service: DocumentQAService):
    """Verify that ambiguous queries facing conflicting competing rules in the same section abstain cleanly."""
    excerpt = CitedExcerptItem(
        document_id="77777777-7777-7777-7777-777777777777",
        document_title="Merchant Settlement Guidelines",
        section_title="Payout Timelines",
        page_number=4,
        score=0.90,
        excerpt=(
            "Standard payout settlement period requires 3 business days following transaction capture. "
            "Expedited payout settlement period delivers funds on a same-day basis within 4 hours."
        ),
    )

    # Query without specifying standard or expedited
    query = "What is the payout settlement period for merchant transactions?"
    ans, is_grounded, best_item = await qa_service._synthesize_grounded_answer(query, [excerpt])
    # Must abstain because it cannot determine which modifier applies
    assert is_grounded is False
    assert "competing rules" in ans.lower() or "not contain sufficient information" in ans.lower()


@pytest.mark.asyncio
async def test_alphanumeric_identifier_discrimination(qa_service: DocumentQAService):
    """Verify exact alphanumeric identifier discrimination between similar rules."""
    excerpt = CitedExcerptItem(
        document_id="88888888-8888-8888-8888-888888888888",
        document_title="FX Volatility Controls",
        section_title="Circuit Breakers",
        page_number=1,
        score=0.93,
        excerpt=(
            "Global Settlement Guideline GS-7712:\n"
            "Emergency currency conversion halts occur when the EUR/USD 5-minute volatility threshold exceeds 3.45%.\n"
            "Global Settlement Guideline GS-9920:\n"
            "Emergency currency conversion halts occur when the GBP/USD 5-minute volatility threshold exceeds 6.20%."
        ),
    )

    # Query specifically for GS-7712
    ans_7712, g_7712, _ = await qa_service._synthesize_grounded_answer(
        "What is the volatility threshold for emergency currency conversion halts under GS-7712?", [excerpt]
    )
    assert g_7712 is True
    assert "3.45%" in ans_7712
    assert "6.20%" not in ans_7712

    # Query specifically for GS-9920
    ans_9920, g_9920, _ = await qa_service._synthesize_grounded_answer(
        "What is the volatility threshold for emergency currency conversion halts under GS-9920?", [excerpt]
    )
    assert g_9920 is True
    assert "6.20%" in ans_9920
    assert "3.45%" not in ans_9920

    # Query for nonexistent GS-3300
    ans_none, g_none, _ = await qa_service._synthesize_grounded_answer(
        "What is the volatility threshold for emergency currency conversion halts under GS-3300?", [excerpt]
    )
    assert g_none is False
    assert "does not contain sufficient information" in ans_none


@pytest.mark.asyncio
async def test_adversarial_rule_id_with_unrelated_predicate_must_abstain(qa_service: DocumentQAService):
    """Verify that asking an unrelated substantive question about a rule ID does not falsely match on the rule ID alone."""
    excerpt = CitedExcerptItem(
        document_id="99999999-9999-9999-9999-999999999999",
        document_title="VanguardPay Enterprise Merchant Agreement 2027",
        section_title="Section 7: SEPA Core Settlement & Indemnity Guarantees",
        page_number=1,
        score=0.95,
        excerpt=(
            "In compliance with SEPA Core clearing regulations, outbound SEPA direct debit reversals require a mandatory escrow indemnity guarantee of 750.00 EUR held for 45 business days. "
            "The full indemnity guarantee remains irrevocably in force across SEPA Core payment schemes, and standard indemnity release rules do not grant waiver of liability without formal counterparty consent. "
            "Partial indemnity release is prohibited under rule VP-SEPA-401, requiring complete restitution before any subsequent claim closure."
        ),
    )

    # Adversarial query: Rule ID exists in sentence, but predicate is completely unrelated (paper check clearing timeframe)
    adv_query = "What is the paper check clearing timeframe under VP-SEPA-401?"
    ans_adv, g_adv, _ = await qa_service._synthesize_grounded_answer(adv_query, [excerpt])
    assert g_adv is False, f"Expected engine to abstain on unrelated predicate under rule ID, but got answer: {ans_adv}"
    assert "does not contain sufficient information" in ans_adv

    # Legitimate query: Rule ID and substantive concepts (partial indemnity release) match
    legit_query = "Is partial indemnity release permitted for SEPA direct debit reversals under VP-SEPA-401?"
    ans_legit, g_legit, _ = await qa_service._synthesize_grounded_answer(legit_query, [excerpt])
    assert g_legit is True
    assert "prohibited under rule VP-SEPA-401" in ans_legit

