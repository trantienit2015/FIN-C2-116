"""AgentCore Platform v1.0 - FIN-C2-116 AdviceTypeClassifyNode (inner subgraph).

CRITICAL regime gate: classifies the described AI output as "regulated
investment advice" (投資助言業者 registration required) vs "non-regulated
information provision" per 金商法 Art. 2-8 + FSA guidance. Classification
is grounded strictly in retrieved_clauses from FIEACorpusRetrieveNode - not
free LLM judgment.
"""

from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

from src.schemas.state import from_json, to_json
from src.services.service import classify_advice_type


class AdviceTypeClassifyNode(FunctionNode):
    """Classify the query as advice-regime vs information-regime, grounded in retrieved clauses."""

    # Inner subgraph node - trust authenticated once at the outer backbone.
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.ANONYMOUS

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        envelope = from_json(state.get("user_input"), {})
        query = envelope.get("query", "")
        retrieved_clauses = from_json(state.get("retrieved_clauses", ""), [])

        if not query:
            emit_trace_event("advice_regime_classify_blocked", {"reason": "query_missing"}, state)
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["AdviceTypeClassifyNode: query missing from envelope"],
            }

        if not retrieved_clauses:
            emit_trace_event("advice_regime_classify_blocked", {"reason": "no_retrieved_clauses"}, state)
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["AdviceTypeClassifyNode: no retrieved clauses to ground the regime classification"],
            }

        regime_label, regime_basis = classify_advice_type(query, retrieved_clauses)

        # S-4: domain event for the CRITICAL regime determination - label + basis count only.
        emit_trace_event(
            "advice_regime_classified",
            {"regime_label": regime_label, "basis_clause_count": len(regime_basis)},
            state,
        )

        return {
            "regime_label": regime_label,
            "regime_basis": to_json(regime_basis),
            "status": AgentStatus.SUCCESS.value,
        }
