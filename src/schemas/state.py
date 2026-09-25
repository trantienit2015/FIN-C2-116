"""AgentCore Platform v1.0 - FIN-C2-116 state schema.

Retail Investor AI Investment Advice Disclosure & FIEA Compliance Q&A Agent.
Flat TypedDict extension of AgentState (ADR-005). Structured payloads
(dict/list) are JSON-string-encoded before being stored in state fields.
"""

import json
from typing import Any, NotRequired

from framework.schemas.agent_state import AgentState


def to_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def from_json(value: str | None, default: Any = None) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


# Type-check note: the wheel ships no py.typed, so mypy resolves AgentState to Any and
# reports every NotRequired below as valid-type. The fields are correct -- the report is a
# packaging artifact, suppressed per field. Drop these ignores once the wheel ships py.typed.
class State(AgentState):
    """Agent state for FIN-C2-116.

    query_text: normalized staff/compliance-officer question.
    retrieved_clauses: JSON list[dict] of matched clauses (clause_id, text,
      score, provision_type) from the FIEA/FSA AI-disclosure KB.
    regime_label: "advice" | "information" - the AdviceTypeClassify verdict.
    regime_basis: JSON list[str] of clause_ids the classification is grounded in.
    disclosure_requirements: JSON list[dict] of matched disclosure requirement
      entries for the classified regime.
    disclosure_template: generated disclosure-wording template snippet.
    validated_answer: final S-3-validated answer text returned to the caller.
    """

    query_text: NotRequired[str]  # type: ignore[valid-type]
    retrieved_clauses: NotRequired[str]  # type: ignore[valid-type]
    regime_label: NotRequired[str]  # type: ignore[valid-type]
    regime_basis: NotRequired[str]  # type: ignore[valid-type]
    disclosure_requirements: NotRequired[str]  # type: ignore[valid-type]
    disclosure_template: NotRequired[str]  # type: ignore[valid-type]
    validated_answer: NotRequired[str]  # type: ignore[valid-type]
