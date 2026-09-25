"""AgentCore Platform v1.0 - FIN-C2-116 TemplateGenerateNode (inner subgraph).

LLM-optional in a real deployment; deterministic fallback keeps the pipeline
runnable without an LLM. Synthesizes the citation-grounded disclosure
wording template from the classified regime, matched requirements, and
retrieved clauses.
"""

from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

from src.schemas.state import from_json
from src.services.service import LLMGenerationError, generate_disclosure_template


class TemplateGenerateNode(FunctionNode):
    """Generate the disclosure-wording template, grounded in matched requirements + retrieved clauses."""

    # Inner subgraph node - trust authenticated once at the outer backbone.
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.ANONYMOUS

    def __init__(self, llm: Any = None) -> None:
        super().__init__()
        self._llm = llm

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        regime_label = state.get("regime_label", "")
        requirements = from_json(state.get("disclosure_requirements", ""), [])
        retrieved_clauses = from_json(state.get("retrieved_clauses", ""), [])

        if not regime_label:
            emit_trace_event("disclosure_template_generate_blocked", {"reason": "regime_label_missing"}, state)
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["TemplateGenerateNode: regime_label missing - AdviceTypeClassifyNode must run first"],
            }

        try:
            template = generate_disclosure_template(regime_label, requirements, retrieved_clauses, llm=self._llm)
        except LLMGenerationError as exc:
            # A CONFIGURED llm that fails/returns unusable content must surface
            # as ERROR, not silently degrade to the deterministic fallback -
            # that fallback is reserved for the llm=None (no LLM configured) case.
            emit_trace_event("disclosure_template_generate_blocked", {"reason": "llm_generation_failed"}, state)
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": [f"TemplateGenerateNode: {exc}"],
            }

        # S-4: domain event for the generation step - length only, no raw content.
        emit_trace_event("disclosure_template_generated", {"template_length": len(template)}, state)

        return {
            "disclosure_template": template,
            "status": AgentStatus.SUCCESS.value,
        }
