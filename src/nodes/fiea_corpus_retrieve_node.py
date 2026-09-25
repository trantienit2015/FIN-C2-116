"""AgentCore Platform v1.0 - FIN-C2-116 FIEACorpusRetrieveNode (inner subgraph).

Hybrid-style (deterministic keyword-match fallback for dense+sparse) vector
search over the 金商法 2026 AI-disclosure KB. Runs first inside the inner
subgraph - receives the {query} envelope forwarded by AdviceDisclosureGraphNode.
"""

from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

from src.schemas.state import from_json, to_json
from src.services.service import retrieve_fiea_clauses


class FIEACorpusRetrieveNode(FunctionNode):
    """Retrieve grounding clauses from the FIEA/FSA AI-disclosure KB."""

    # Inner subgraph node - trust authenticated once at the outer backbone.
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.ANONYMOUS

    def __init__(self, kb: list[dict[str, Any]] | None = None, top_k: int = 8) -> None:
        super().__init__()
        self._kb = kb or []
        self._top_k = top_k

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        envelope = from_json(state.get("user_input"), {})
        query = envelope.get("query", "")

        if not query:
            emit_trace_event("fiea_clauses_retrieve_blocked", {"reason": "query_missing"}, state)
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["FIEACorpusRetrieveNode: query missing from envelope"],
            }

        retrieved_clauses = retrieve_fiea_clauses(query, kb=self._kb, top_k=self._top_k)

        # S-4: domain event for the KB lookup - hit count only, no raw query/passage content.
        emit_trace_event("fiea_clauses_retrieved", {"retrieved_count": len(retrieved_clauses)}, state)

        return {
            "retrieved_clauses": to_json(retrieved_clauses),
            "status": AgentStatus.SUCCESS.value,
        }
