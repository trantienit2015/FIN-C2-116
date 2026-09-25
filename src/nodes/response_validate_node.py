"""AgentCore Platform v1.0 - FIN-C2-116 ResponseValidateNode (outer post_process slot).

S-3 deterministic clause-grounding gate: every clause reference in the
final answer must be present in retrieved_clauses (no fabricated citation),
and the mandatory qualified-counsel disclaimer must be present (no
legal-opinion-style assertion may replace it). Own-dict field re-check
only (S-3 self-consistency rule).
"""

from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

from src.schemas.state import from_json
from src.services.service import has_unsourced_citation, is_missing_mandatory_disclaimer


class ResponseValidateNode(FunctionNode):
    """Validate the disclosure template cites only retrieved clauses and carries the mandatory disclaimer."""

    # Outer node - trust must match agent.yaml's agent-level required_trust_level.
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        disclosure_template = state.get("disclosure_template", "")
        retrieved_clauses = from_json(state.get("retrieved_clauses", ""), [])

        if has_unsourced_citation(disclosure_template, retrieved_clauses):
            emit_trace_event("response_validate_blocked", {"reason": "unsourced_citation"}, state)
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["ResponseValidateNode: answer cites a clause not present in retrieved_clauses"],
            }

        if is_missing_mandatory_disclaimer(disclosure_template):
            emit_trace_event("response_validate_blocked", {"reason": "disclaimer_missing"}, state)
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["ResponseValidateNode: mandatory qualified-counsel disclaimer missing from answer"],
            }

        # S-4: domain event for the regulatory determination answered - regime + clause count, no raw content.
        emit_trace_event(
            "advice_disclosure_query_answered",
            {"regime_label": state.get("regime_label", ""), "clause_count": len(retrieved_clauses)},
            state,
        )

        # The S-3 hook below receives only this returned dict, not the accumulated state,
        # so the fields it re-checks are echoed here.
        return {
            "validated_answer": disclosure_template,
            "formatted_output": disclosure_template,
            "disclosure_template": disclosure_template,
            "retrieved_clauses": state.get("retrieved_clauses", ""),
            "status": AgentStatus.SUCCESS.value,
        }

    def _extra_security_gate_output(self, state: dict[str, Any]) -> dict[str, Any]:
        """Non-suppressible re-check on the output dict's own fields."""
        if state.get("status") == AgentStatus.ERROR.value:
            return state  # already rejected by execute(); keep its error_log
        disclosure_template = state.get("disclosure_template", "")
        retrieved_clauses = from_json(state.get("retrieved_clauses", ""), [])

        if has_unsourced_citation(disclosure_template, retrieved_clauses) or is_missing_mandatory_disclaimer(
            disclosure_template
        ):
            emit_trace_event("response_validate_s3_recheck_blocked", {}, state)
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["ResponseValidateNode: S-3 re-check blocked an unsourced or disclaimer-missing answer"],
            }
        return state
