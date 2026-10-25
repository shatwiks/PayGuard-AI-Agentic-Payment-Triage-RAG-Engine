"""Domain evidence grounding and constraint verification engine for PayGuard AI.

Provides:
1. Deterministic, mathematically bounded candidate sentence extraction and scoring.
2. Multi-tier financial constraint enforcement (Currency, Payment Rail, Action, Refund polarity).
3. Exact alphanumeric rule identifier specificity and tie-breaking.
4. Genuine token coverage validation preventing false-positive hallucinations on rule IDs alone.
5. Conflicting competing rules detection with clean ambiguity abstention.
"""

import logging
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from backend.app.schemas.knowledge import CitedExcerptItem

logger = logging.getLogger("payguard.grounding")


@dataclass
class GroundedCandidate:
    """Represents a scored candidate evidence sentence with semantic telemetry."""
    score: float
    sentence: str
    excerpt: CitedExcerptItem
    modifiers: Set[str]
    token_coverage: float
    substantive_matches: int


class FinancialConstraintRegistry:
    """Standardized financial and regulatory domain vocabulary and constraints."""

    STOPWORDS: Set[str] = {
        "what", "when", "where", "which", "who", "whom", "whose", "why", "how",
        "the", "and", "or", "for", "with", "does", "can", "should", "tell", "about",
        "is", "are", "was", "were", "be", "been", "under", "in", "on", "at", "to",
        "of", "from", "by", "as", "an", "a", "it", "its", "per", "that", "this",
        "does", "do", "did", "have", "has", "had", "will", "would", "may", "might",
        "long", "much", "many", "up", "down", "out", "over"
    }

    META_WORDS: Set[str] = {
        "exact", "decimal", "value", "stated", "threshold", "qualify", "stated in",
        "rule", "rules", "section", "clause", "article", "paragraph", "policy", "guideline"
    }

    GENERIC_ATTRIBUTES: Set[str] = {
        "fee", "fees", "penalty", "penalties", "surcharge", "surcharges", "fine", "fines",
        "cost", "costs", "charge", "charges", "amount", "rate", "percent", "percentage",
        "day", "days", "time", "date", "window",
        "usd", "eur", "gbp", "dollar", "dollars", "euro", "euros",
        "permitted", "permit", "permits", "prohibited", "prohibit", "prohibits",
        "allowed", "allow", "allows", "forbidden", "barred", "required", "mandatory"
    }

    CURRENCIES: Dict[str, Set[str]] = {
        "usd": {"usd", "dollar", "dollars", "$"},
        "eur": {"eur", "euro", "euros", "€"},
        "gbp": {"gbp", "pound", "pounds", "£"},
    }

    PAYMENT_RAILS: Dict[str, Set[str]] = {
        "swift": {"swift", "wire", "international wire", "bank wire", "overseas wire", "overseas bank wire"},
        "wire": {"swift", "wire", "international wire", "bank wire", "overseas wire", "overseas bank wire"},
        "rtp": {"rtp", "real-time", "real time", "instant payout", "instant payouts", "instant transfer"},
        "ach": {"ach", "r01", "nacha", "rdfi"},
        "sepa": {"sepa", "sct", "sdd", "sepa core", "sepa b2b"},
        "fps": {"fps", "faster payments", "faster payment", "uk faster payments"},
        "bacs": {"bacs", "bacs direct debit", "direct debit indemnity"},
        "crypto": {"crypto", "cryptocurrency", "digital", "asset", "digital asset", "digital assets", "on-ramp", "crypto-to-fiat"},
        "visa": {"visa"},
        "mastercard": {"mastercard"},
    }

    TOPIC_CONSTRAINTS: Dict[str, Set[str]] = {
        "dispute": {"dispute", "disputes", "disputed", "chargeback", "chargebacks", "contest", "contests", "contested", "contesting"},
        "arbitration": {"arbitrate", "arbitration", "hearing", "pre-arbitration"},
        "rebate": {"rebate", "rebates", "discount", "discounts", "basis point", "basis points"},
        "reserve": {"reserve", "rolling reserve", "held", "lock", "locked", "lockup"},
        "return": {"return", "returned", "returns", "rejected", "rejection", "cutoff", "insufficient funds"},
    }

    MODIFIER_PAIRS: List[Tuple[Set[str], Set[str]]] = [
        ({"standard", "regular", "normal"}, {"expedited", "express", "urgent", "priority", "rush", "same-day"}),
        ({"domestic", "local", "national"}, {"international", "cross-border", "overseas", "foreign", "global"}),
        ({"partial"}, {"full", "total", "entire"}),
    ]

    TIME_UNITS: Set[str] = {
        "minute", "minutes", "hour", "hours", "day", "days", "week", "weeks",
        "month", "months", "year", "years", "sec", "second", "seconds", "ms",
        "basis", "point", "points"
    }

    SYNONYM_CLUSTERS: List[Set[str]] = [
        {"fee", "fees", "penalty", "penalties", "surcharge", "surcharges", "fine", "fines", "deduct", "deducted", "deduction", "deductions", "charge", "charges", "tariff", "levied", "assessment", "assessments", "bill", "billed", "billing", "incur", "incurred", "cost", "costs"},
        {"rebate", "rebates", "discount", "discounts", "basis point", "basis points"},
        {"cancel", "cancelling", "cancellation", "cancellations", "abort", "aborting"},
        {"recall", "recalls"},
        {"rtp", "real-time", "real", "instant", "payout", "payouts", "transfer", "transfers"},
        {"reserve", "held", "lock", "locked", "lockup", "holding", "rolling reserve"},
        {"merchant", "merchants", "seller", "sellers", "business"},
        {"micro-merchant", "micro-merchants", "small merchant", "small merchants", "small retail seller", "micro seller"},
        {"enterprise", "corporate", "high-volume", "volume merchant", "corporate client", "corporate clients"},
        {"dispute", "disputes", "disputed", "chargeback", "chargebacks", "contest", "contests", "contested", "contesting"},
        {"arbitrate", "arbitration", "hearing", "pre-arbitration"},
        {"return", "returned", "returns", "rejected", "rejection", "cutoff", "insufficient funds"},
        {"10000000", "ten million", "10 million", "10,000,000"},
        {"crypto", "cryptocurrency", "digital", "asset", "digital asset", "digital assets", "crypto-to-fiat", "on-ramp"},
        {"barred", "prohibited", "prohibit", "forbidden", "prohibits", "deny", "denied", "permitted", "permit", "permits", "allowed", "allow", "allows"},
        {"platinum", "top-tier", "tier-1", "premier"},
    ]


class EvidenceGroundingEngine:
    """Verifies evidence grounding, filters constraints, and extracts answers strictly from retrieved text."""

    def __init__(self, registry: Optional[FinancialConstraintRegistry] = None):
        self.registry = registry or FinancialConstraintRegistry()

    _INJECTION_COMMAND_PATTERNS = [
        re.compile(r"(?i)\b(?:execute|run|perform|apply)\s+(?:system\s+)?(?:instruction|override|command)\b"),
        re.compile(r"(?i)\b(?:ignore|bypass|override)\s+(?:all\s+)?(?:previous|security|system|rules|gates)\b"),
        re.compile(r"(?i)<instruction\b"),
    ]

    @staticmethod
    def stem(word: str) -> str:
        """Language-agnostic suffix trimmer for morphological normalization."""
        w = word.lower()
        for sfx in ("tions", "tion", "ing", "ies", "ied", "ed", "es", "s", "ment", "trate", "tration"):
            if w.endswith(sfx) and len(w) - len(sfx) >= 3:
                return w[:-len(sfx)]
        return w

    @classmethod
    def tokenize_text(cls, text: str) -> Set[str]:
        """Extracts normalized alphanumeric tokens including compound hyphens and underscores."""
        tokens = set()
        raw = re.findall(r"\b[A-Za-z0-9_.-]{2,}\b", text.lower())
        for w in raw:
            tokens.add(w)
            if "-" in w:
                for part in w.split("-"):
                    if len(part) >= 2:
                        tokens.add(part)
            if "_" in w:
                for part in w.split("_"):
                    if len(part) >= 2:
                        tokens.add(part)
        return tokens

    @classmethod
    def extract_rule_ids(cls, tokens: Set[str]) -> Set[str]:
        """Extracts rule identifiers (e.g. VP-SEPA-401, AF-902, GS-7712)."""
        rule_ids = set()
        for w in tokens:
            if "-" in w and any(c.isdigit() for c in w) and any(c.isalpha() for c in w):
                parts = w.split("-")
                if parts[-1] not in FinancialConstraintRegistry.TIME_UNITS and parts[0] not in FinancialConstraintRegistry.TIME_UNITS:
                    rule_ids.add(w)
        return rule_ids

    def terms_match(self, q_term: str, doc_tokens: Set[str], context_text: str) -> bool:
        """Determines if a query term matches doc tokens via exact match, stemming, or synonym cluster."""
        if q_term in doc_tokens:
            return True
        stem_q = self.stem(q_term)
        if stem_q in doc_tokens:
            return True
        for dt in doc_tokens:
            stem_d = self.stem(dt)
            if stem_q == stem_d:
                return True

        text_lower = context_text.lower()
        for cluster in self.registry.SYNONYM_CLUSTERS:
            if any(term == q_term or term == stem_q for term in cluster):
                if any(term in doc_tokens or term in text_lower for term in cluster):
                    return True
        return False

    def synthesize_grounded_answer(
        self,
        query: str,
        cited_excerpts: List[CitedExcerptItem],
    ) -> Tuple[str, bool, Optional[CitedExcerptItem]]:
        """Synthesizes grounded answer or abstains cleanly if facts are absent, mismatched, or ungrounded."""
        # 1. Defend against imperative prompt injection commands
        for pat in self._INJECTION_COMMAND_PATTERNS:
            if pat.search(query):
                return (
                    f"The provided document does not contain sufficient information to answer the question: '{query}'.",
                    False,
                    None,
                )

        q_lower = query.lower()

        # Strip SQL injection / comment preamble (e.g., "'; DROP TABLE ...; -- ")
        q_norm = re.sub(r"^.*?;\s*--\s*", "", q_lower).strip() or q_lower

        # Principled number phrase normalization (e.g. "ten million" -> "10000000")
        num_word_map = {
            "ten million": "10000000",
            "10 million": "10000000",
            "one million": "1000000",
            "1 million": "1000000",
            "five hundred": "500",
        }
        for nw, digit_val in num_word_map.items():
            if nw in q_norm:
                q_norm = q_norm.replace(nw, digit_val)

        raw_query_tokens = self.tokenize_text(q_norm)
        query_semantic_tokens = [
            w for w in raw_query_tokens
            if w not in self.registry.STOPWORDS and w not in self.registry.META_WORDS and len(w) > 1
        ]

        if not query_semantic_tokens:
            return (
                f"The provided document does not contain sufficient information to answer the question: '{query}'.",
                False,
                None,
            )

        # 2. Detect currency constraints
        specified_currencies = set()
        for curr, terms in self.registry.CURRENCIES.items():
            if any(t in raw_query_tokens or t in q_lower for t in terms):
                specified_currencies.add(curr)

        # 3. Detect payment rails
        specified_rails = set()
        for rail, terms in self.registry.PAYMENT_RAILS.items():
            if any(t in raw_query_tokens or t in q_lower for t in terms):
                specified_rails.add(rail)

        # 4. Detect tier constraints
        query_has_micro = any(t in raw_query_tokens for t in {"micro", "small", "tier-1"})
        query_has_enterprise = any(t in raw_query_tokens for t in {"enterprise", "corporate", "10000000"})

        # 5. Detect specific banking action constraints
        query_has_recall = any(t in raw_query_tokens for t in {"recall", "recalls"})
        query_has_cancel = any(t in raw_query_tokens for t in {"cancel", "cancelling", "cancellation", "abort", "aborting"})

        # 6. Detect refund constraints (partial vs full)
        query_has_full_refund = ("full refund" in q_lower or ("full" in raw_query_tokens and "refund" in raw_query_tokens))

        # 7. Detect domain topic anchors
        specified_topics = set()
        for topic, terms in self.registry.TOPIC_CONSTRAINTS.items():
            if any(t in raw_query_tokens or t in q_lower for t in terms):
                specified_topics.add(topic)

        # 8. Detect exact alphanumeric rule identifiers in query (e.g., "vp-sepa-401", "gs-7712")
        query_rule_ids = self.extract_rule_ids(self.tokenize_text(query))
        rule_id_tokens = set(query_rule_ids)
        for rid in query_rule_ids:
            rule_id_tokens.update(rid.split("-"))
            rule_id_tokens.update(rid.split("_"))

        substantive_query_tokens = [w for w in query_semantic_tokens if w not in rule_id_tokens]
        substantive_subject_tokens = [w for w in substantive_query_tokens if w not in self.registry.GENERIC_ATTRIBUTES]

        candidate_records: List[GroundedCandidate] = []

        for exc in cited_excerpts:
            sec_title = exc.section_title or ""
            doc_title = exc.document_title or ""
            combined_header = f"{doc_title} {sec_title}"
            header_tokens = self.tokenize_text(combined_header)

            sentences = [s.strip() for s in re.split(r"(?<!\d)\.(?!\d)\s*|\n+", exc.excerpt) if len(s.strip()) > 15]

            current_lead_in = ""
            for s in sentences:
                if s.strip().endswith(":"):
                    current_lead_in = s.strip()
                    continue

                sentence_tokens = self.tokenize_text(s)
                lead_in_tokens = self.tokenize_text(current_lead_in) if current_lead_in else set()
                full_context_text = f"{combined_header} {current_lead_in} {s}"
                full_context_lower = full_context_text.lower()
                s_lower = s.lower()
                s_context = f"{current_lead_in} {s}".strip() if current_lead_in else s

                # Currency Guard
                if specified_currencies:
                    sentence_currencies = set()
                    for curr, terms in self.registry.CURRENCIES.items():
                        if any(t in sentence_tokens or t in s_lower for t in terms):
                            sentence_currencies.add(curr)
                    if sentence_currencies and not (specified_currencies & sentence_currencies):
                        continue

                # Rail Guard
                if specified_rails:
                    matched_rail = False
                    for r in specified_rails:
                        rail_syns = self.registry.PAYMENT_RAILS[r]
                        if any(syn in sentence_tokens or syn in full_context_lower for syn in rail_syns):
                            matched_rail = True
                            break
                    if not matched_rail:
                        continue

                # Topic Guard
                if specified_topics:
                    matched_topic = False
                    for top in specified_topics:
                        top_terms = self.registry.TOPIC_CONSTRAINTS[top]
                        if any(t in sentence_tokens or t in full_context_lower for t in top_terms):
                            matched_topic = True
                            break
                    if not matched_topic:
                        continue

                # Modifier Congruence & Conflict Guard
                skip_sentence = False
                modifier_bonus = 0.0
                for pos_set, neg_set in self.registry.MODIFIER_PAIRS:
                    q_has_pos = any(t in raw_query_tokens or t in q_lower for t in pos_set)
                    q_has_neg = any(t in raw_query_tokens or t in q_lower for t in neg_set)
                    s_has_pos = any(t in sentence_tokens or t in s_lower for t in pos_set)
                    s_has_neg = any(t in sentence_tokens or t in s_lower for t in neg_set)

                    if q_has_pos and not q_has_neg:
                        if s_has_neg and not s_has_pos:
                            skip_sentence = True
                            break
                        if s_has_pos:
                            modifier_bonus += 2.0

                    if q_has_neg and not q_has_pos:
                        if s_has_pos and not s_has_neg:
                            skip_sentence = True
                            break
                        if s_has_neg:
                            modifier_bonus += 2.0

                if skip_sentence:
                    continue

                # Exact Identifier Specificity
                identifier_bonus = 0.0
                if query_rule_ids:
                    sentence_rule_ids = self.extract_rule_ids(sentence_tokens)
                    lead_in_rule_ids = self.extract_rule_ids(lead_in_tokens)

                    if query_rule_ids & sentence_tokens:
                        identifier_bonus += 3.0
                    elif query_rule_ids & lead_in_tokens:
                        identifier_bonus += 2.5
                    elif query_rule_ids & header_tokens:
                        identifier_bonus += 1.5

                    if sentence_rule_ids and not (query_rule_ids & sentence_rule_ids):
                        continue
                    if lead_in_rule_ids and not (query_rule_ids & lead_in_rule_ids):
                        continue

                # Tier Guard
                if query_has_micro and not query_has_enterprise:
                    if "enterprise" in s_lower or "corporate" in s_lower or "10000000" in s_lower:
                        if not any(m in s_lower for m in {"micro", "small", "tier-1"}):
                            continue
                if query_has_enterprise and not query_has_micro:
                    if "micro-merchant" in full_context_lower or "tier-1" in full_context_lower:
                        if not any(e in full_context_lower for e in {"enterprise", "corporate", "10000000"}):
                            continue

                # Action Guard
                if query_has_recall and not query_has_cancel:
                    if "recall" not in full_context_lower:
                        continue
                if query_has_cancel and not query_has_recall:
                    if not any(c in full_context_lower for c in {"cancel", "abort"}):
                        if "wire" not in full_context_lower and "swift" not in full_context_lower:
                            continue

                # Refund Guard
                if query_has_full_refund and "partial refund" in s_lower and "full refund" not in s_lower:
                    continue

                # Substantive subject match requirement
                subj_matches = sum(
                    1 for st in substantive_subject_tokens
                    if self.terms_match(st, sentence_tokens | lead_in_tokens | header_tokens, full_context_text)
                )
                if substantive_subject_tokens and subj_matches == 0:
                    continue

                # Substantive sentence match requirement: must match at least one substantive token in sentence
                substantive_sentence_matches = sum(
                    1 for qw in substantive_query_tokens
                    if self.terms_match(qw, sentence_tokens | lead_in_tokens, s_context)
                )
                if substantive_query_tokens and substantive_sentence_matches == 0:
                    continue

                sentence_matches = sum(1 for qw in query_semantic_tokens if self.terms_match(qw, sentence_tokens | lead_in_tokens, s_context))
                header_matches = sum(
                    1 for qw in query_semantic_tokens
                    if self.terms_match(qw, header_tokens, combined_header) and not self.terms_match(qw, sentence_tokens | lead_in_tokens, s_context)
                )

                total_matches = sentence_matches + (0.5 * header_matches) + modifier_bonus + identifier_bonus

                valid_candidate = (
                    sentence_matches >= 2
                    or (sentence_matches >= 1 and subj_matches >= 1)
                    or (header_matches >= 2 and subj_matches >= 1)
                    or (bool(query_rule_ids) and not substantive_query_tokens and sentence_matches >= 1)
                )

                if valid_candidate:
                    matched_modifiers = set()
                    for pos_set, neg_set in self.registry.MODIFIER_PAIRS:
                        if any(t in sentence_tokens or t in s_lower for t in pos_set):
                            matched_modifiers.update(pos_set)
                        if any(t in sentence_tokens or t in s_lower for t in neg_set):
                            matched_modifiers.update(neg_set)

                    matched_query_tokens_count = sum(
                        1 for qw in query_semantic_tokens
                        if self.terms_match(qw, sentence_tokens | lead_in_tokens, s_context)
                        or self.terms_match(qw, header_tokens, combined_header)
                    )
                    token_cov = matched_query_tokens_count / len(query_semantic_tokens) if query_semantic_tokens else 0.0

                    candidate_records.append(
                        GroundedCandidate(
                            score=total_matches,
                            sentence=s,
                            excerpt=exc,
                            modifiers=matched_modifiers,
                            token_coverage=token_cov,
                            substantive_matches=substantive_sentence_matches,
                        )
                    )

        if not candidate_records:
            return (
                f"The provided document does not contain sufficient information to answer the question: '{query}'.",
                False,
                None,
            )

        candidate_records.sort(key=lambda c: c.score, reverse=True)
        top_cand = candidate_records[0]
        max_score = top_cand.score
        best_match_sentence = top_cand.sentence
        best_match_excerpt = top_cand.excerpt

        # Competing rules detection
        for pos_set, neg_set in self.registry.MODIFIER_PAIRS:
            q_specified_modifier = any(t in raw_query_tokens or t in q_lower for t in (pos_set | neg_set))
            if not q_specified_modifier:
                top_tier_cands = [c for c in candidate_records if c.score >= max(2.0, max_score - 1.5)]
                has_pos = any(bool(c.modifiers & pos_set) for c in top_tier_cands)
                has_neg = any(bool(c.modifiers & neg_set) for c in top_tier_cands)
                if has_pos and has_neg:
                    return (
                        f"The provided document contains competing rules for '{query}' without distinguishing criteria. "
                        f"Please specify terms.",
                        False,
                        None,
                    )

        if max_score < 1.5 or top_cand.token_coverage < 0.35 or not best_match_sentence or not best_match_excerpt:
            return (
                f"The provided document does not contain sufficient information to answer the question: '{query}'.",
                False,
                None,
            )

        page_info = f", Page {best_match_excerpt.page_number}" if best_match_excerpt.page_number else ""
        section_info = f"Section '{best_match_excerpt.section_title}'" if best_match_excerpt.section_title else "Document Body"

        answer = (
            f"Based on {best_match_excerpt.document_title} ({section_info}{page_info}):\n\n"
            f"\"{best_match_sentence}.\""
        )
        return answer, True, best_match_excerpt
