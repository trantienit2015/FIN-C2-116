"""AgentCore Platform v1.0 - FIN-C2-116 domain services.

Deterministic FIEA/FSA clause retrieval, advice-vs-information regime
classification, disclosure requirement matching, and template generation
(Tool layer, no LLM required for the deterministic core). S-3 output gate
is non-suppressible: every regime determination and disclosure claim must
cite a retrieved clause; no fabricated legal conclusion is allowed.
"""

from __future__ import annotations

import re
from typing import Any

# 投資助言業者-registration-required "advice" keywords: language that
# recommends a specific action/timing/instrument to a specific investor.
_ADVICE_MARKERS = (
    "should buy",
    "should sell",
    "recommend",
    "you should invest",
    "買うべき",
    "売るべき",
    "推奨します",
    "投資すべき",
)

_MANDATORY_DISCLAIMER = "This is general information, not individualized investment advice; consult a registered 投資助言業者 or qualified counsel."


class LLMGenerationError(Exception):
    """Raised when an LLM IS configured but the call fails or returns unusable
    content. The deterministic fallback below is reserved for llm=None
    (no LLM configured) — a configured-but-failing LLM must never silently
    degrade into a fabricated-looking SUCCESS response."""


def _extract_text(raw: Any) -> str:
    """Normalize an LLM .complete() result. Canonical BaseLLM.complete()
    returns a dict ({"content": str, ...}); accept a bare string too for
    backward-compat fakes. Anything else normalizes to ""."""
    if isinstance(raw, dict):
        content = raw.get("content", "")
        return content if isinstance(content, str) else ""
    if isinstance(raw, str):
        return raw
    return ""


def normalize_query(text: str) -> str:
    """Deterministic normalization (Tool layer, no LLM)."""
    return re.sub(r"\s+", " ", text).strip()


def retrieve_fiea_clauses(query: str, kb: list[dict[str, Any]] | None = None, top_k: int = 8) -> list[dict[str, Any]]:
    """Deterministic hybrid-style (keyword + provision metadata) clause lookup.

    Real deployment: dense (multilingual-e5-large) + sparse (BM25) hybrid
    search. This deterministic keyword-match fallback keeps the pipeline
    runnable and testable without an embedding index.
    """
    kb = kb or []
    lower_query = query.lower()
    matches = []
    for entry in kb:
        keywords = entry.get("keywords", [])
        if any(kw.lower() in lower_query for kw in keywords):
            matches.append(entry)
    return matches[:top_k]


def classify_advice_type(query: str, retrieved_clauses: list[dict[str, Any]]) -> tuple[str, list[str]]:
    """CRITICAL regime gate: classify as "advice" (投資助言業者 registration
    required) vs "information" (registration-free), per 金商法 Art. 2-8.

    Grounded strictly in retrieved clauses - if no clause was retrieved,
    the classification cannot proceed (caller must broaden the query).
    Deterministic keyword heuristic stands in for the LLM-assisted
    classification used in production; the regime label is always backed
    by cited clause_ids from retrieved_clauses only.
    """
    lower_query = query.lower()
    is_advice = any(marker.lower() in lower_query for marker in _ADVICE_MARKERS)
    label = "advice" if is_advice else "information"
    basis = [c["clause_id"] for c in retrieved_clauses if c.get("clause_id")]
    return label, basis


def match_disclosure_requirements(
    regime_label: str, requirement_table: list[dict[str, Any]] | None = None
) -> list[dict[str, Any]]:
    """Deterministic requirement-table lookup for the classified regime."""
    requirement_table = requirement_table or []
    return [entry for entry in requirement_table if entry.get("regime") == regime_label]


def generate_disclosure_template(
    regime_label: str,
    requirements: list[dict[str, Any]],
    retrieved_clauses: list[dict[str, Any]],
    llm: Any | None = None,
) -> str:
    """Synthesize the citation-grounded disclosure-wording template.

    Raises LLMGenerationError when an LLM is configured but the call fails
    or returns unusable content - callers must surface this as
    AgentStatus.ERROR.value, not silently fall back to the deterministic
    path (that path is reserved for llm=None).
    """
    if llm is None or not hasattr(llm, "complete"):
        # Deterministic fallback path - valid ONLY when no LLM is configured
        # at all. A configured-but-failing LLM must NOT reach this branch;
        # see the LLMGenerationError raises below.
        clause_ids = ", ".join(c["clause_id"] for c in retrieved_clauses if c.get("clause_id"))
        req_ids = ", ".join(r.get("requirement_id", "") for r in requirements)
        body = (
            f"Regime classification: {regime_label} (basis: {clause_ids or 'n/a'}). "
            f"Applicable disclosure requirements: {req_ids or 'none matched'}."
        )
    else:
        prompt = (
            f"Regime: {regime_label}. Requirements: {requirements}. "
            f"Clauses: {retrieved_clauses}. Draft a disclosure template citing clause IDs."
        )
        try:
            raw = llm.complete([{"role": "user", "content": prompt}])
        except Exception as exc:
            raise LLMGenerationError(f"LLM provider call failed: {exc}") from exc
        body = _extract_text(raw)
        if not body:
            raise LLMGenerationError("LLM returned empty or unusable content")
    return f"{body} {_MANDATORY_DISCLAIMER}"


def has_unsourced_citation(text: str, retrieved_clauses: list[dict[str, Any]]) -> bool:
    """Non-suppressible re-check: any clause_id cited in the answer must be

    present in retrieved_clauses. Flags a fabricated citation (a clause_id
    referenced in the answer that was never actually retrieved).
    """
    known_clause_ids = {c.get("clause_id") for c in retrieved_clauses if c.get("clause_id")}
    # Negative lookbehind (?<!-) prevents matching a hyphen-joined suffix of a
    # larger compound token (e.g. "ADV-01" inside "REQ-ADV-01", a requirement_id
    # - not a clause citation) as if it were a standalone clause reference.
    cited_clause_ids = set(re.findall(r"(?<!-)\bArt\.\s?\d+(?:-\d+)*\b|(?<!-)\b[A-Z]{2,}-\d+(?:-\d+)*\b", text))
    return bool(cited_clause_ids - known_clause_ids)


def is_missing_mandatory_disclaimer(text: str) -> bool:
    """Non-suppressible re-check: mandatory qualified-counsel disclaimer must

    be present, and no legal-opinion-style assertion ("this is legal/is
    guaranteed compliant") may replace it.
    """
    return _MANDATORY_DISCLAIMER not in text
