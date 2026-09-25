"""AgentCore Platform v1.0 - FIN-C2-116 outer graph (Cat 2).

Retail Investor AI Investment Advice Disclosure & FIEA Compliance Q&A Agent.

Cat 2: outer AgentBaseGraph with the fixed 5-node backbone. Domain
complexity is encapsulated in AdviceDisclosureGraphNode (the `main` slot),
which wraps the inner AdviceDisclosureWorkflowGraph. Do NOT override
add_edges().

Backbone: initialize -> pre_process(QueryNormalize) -> main(GraphNode)
          -> post_process(ResponseValidate) -> finalize

AdviceDisclosureGraphNode lives here (not under src/nodes/) - the PB-6
invoke-order test only discovers BaseNode subclasses under src/nodes/,
and a GraphNode's __call__ intentionally skips the standard S-2/S-4/S-3
lifecycle (gating is delegated to the inner subgraph).
"""

import json
from typing import Any, ClassVar

from framework.graph.agent_base_graph import AgentBaseGraph
from framework.nodes.graph_node import GraphNode
from framework.schemas.agent_state import AgentState
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

from src.nodes.query_normalize_node import QueryNormalizeNode
from src.nodes.response_validate_node import ResponseValidateNode
from src.schemas.state import State


class AdviceDisclosureGraphNode(GraphNode):
    """Wraps the inner FIEA-retrieve/regime-classify/requirement-match/template-generate workflow (Cat 2 composition)."""

    # S-1: outer main-slot wrapper - first node in the outer backbone
    # receiving caller input. Must match agent.yaml's required_trust_level
    # and sibling outer nodes QueryNormalizeNode/ResponseValidateNode.
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL
    # "propagate": re-raise inner errors as SubgraphError (fail fast - default).
    error_strategy: ClassVar[str] = "propagate"
    # No HITL in this template.
    propagate_hitl: ClassVar[bool] = False

    def __init__(
        self,
        kb: list[dict[str, Any]] | None = None,
        requirement_table: list[dict[str, Any]] | None = None,
        llm: Any = None,
    ) -> None:
        super().__init__()
        self._kb = kb or []
        self._requirement_table = requirement_table or []
        self._llm = llm

    def get_subgraph(self) -> Any:
        from src.graph.domain_workflow_graph import AdviceDisclosureWorkflowGraph

        sg = AdviceDisclosureWorkflowGraph(config=self._parent_config())
        sg.compile()
        return sg

    def extract_input(self, state: AgentState) -> str:
        # S-4: runs inside GraphNode.execute() - audit the dispatch into the inner subgraph.
        emit_trace_event(
            "advice_disclosure_workflow_dispatched", {"correlation_id": state.get("correlation_id", "")}, state
        )
        return json.dumps({"query": state.get("validated_input", state.get("query_text", ""))})

    def merge_output(self, state: AgentState, sub_result: dict[str, Any]) -> dict[str, Any]:
        emit_trace_event(
            "advice_disclosure_workflow_completed",
            {"correlation_id": state.get("correlation_id", ""), "status": str(sub_result.get("status"))},
            state,
        )
        return {
            "retrieved_clauses": sub_result.get("retrieved_clauses"),
            "regime_label": sub_result.get("regime_label"),
            "regime_basis": sub_result.get("regime_basis"),
            "disclosure_requirements": sub_result.get("disclosure_requirements"),
            "disclosure_template": sub_result.get("disclosure_template"),
            "status": sub_result.get("status"),
        }

    def _parent_config(self) -> dict[str, Any]:
        return {"kb": self._kb, "requirement_table": self._requirement_table, "llm": self._llm}


class FINAIAdviceDisclosureAgent(AgentBaseGraph):
    """FIN-C2-116 - Retail Investor AI Investment Advice Disclosure & FIEA Compliance Q&A Agent (Cat 2)."""

    @property
    def name(self) -> str:
        return "fin-c2-116"

    @property
    def state_schema(self) -> type:
        return State

    def register_nodes(self) -> None:
        super().register_nodes()  # injects initialize + finalize

        kb = self.config.get("kb")
        requirement_table = self.config.get("requirement_table")
        llm = self.config.get("llm")

        self._nodes["pre_process"] = QueryNormalizeNode()
        self._nodes["main"] = AdviceDisclosureGraphNode(kb=kb, requirement_table=requirement_table, llm=llm)
        self._nodes["post_process"] = ResponseValidateNode()

    # add_edges() is NOT overridden - backbone wiring belongs to the framework.


# Alias for agent.yaml module:"src.graph" resolution (AgentRegistry / api/server.py).
Graph = FINAIAdviceDisclosureAgent
