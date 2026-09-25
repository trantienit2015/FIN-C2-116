"""AgentCore Platform v1.0 - FIN-C2-116 DisclosureReqMatchNode (inner subgraph).

Matches the classified regime (advice vs information) to the applicable
disclosure requirement set from the requirement table.
"""

from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

from src.schemas.state import to_json
from src.services.service import match_disclosure_requirements


class DisclosureReqMatchNode(FunctionNode):
    """Match the classified regime to its disclosure requirement set."""

    # Inner subgraph node - trust authenticated once at the outer backbone.
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.ANONYMOUS

    def __init__(self, requirement_table: list[dict[str, Any]] | None = None) -> None:
        super().__init__()
        self._requirement_table = requirement_table or []

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        regime_label = state.get("regime_label", "")

        if not regime_label:
            emit_trace_event("disclosure_requirements_match_blocked", {"reason": "regime_label_missing"}, state)
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["DisclosureReqMatchNode: regime_label missing - AdviceTypeClassifyNode must run first"],
            }

        requirements = match_disclosure_requirements(regime_label, requirement_table=self._requirement_table)

        # S-4: domain event for the requirement-matching step - count only.
        emit_trace_event("disclosure_requirements_matched", {"requirement_count": len(requirements)}, state)

        return {
            "disclosure_requirements": to_json(requirements),
            "status": AgentStatus.SUCCESS.value,
        }
