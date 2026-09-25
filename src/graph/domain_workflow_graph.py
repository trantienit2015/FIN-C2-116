"""AgentCore Platform v1.0 - FIN-C2-116 inner domain workflow graph.

Cat 2 inner graph: FIEA/FSA clause retrieval -> advice-vs-information regime
classification -> disclosure requirement matching -> disclosure template
generation. Instantiated by AdviceDisclosureGraphNode.get_subgraph() in graph.py.

Pipeline (linear, fail-fast on ERROR):
    START -> fiea_corpus_retrieve -> advice_type_classify -> disclosure_req_match
          -> template_generate -> END
"""

from typing import Any
from langgraph.graph import END, START

from framework.graph.base_graph import BaseGraph
from framework.schemas.agent_state import AgentState
from framework.schemas.agent_status import AgentStatus

from src.nodes.advice_type_classify_node import AdviceTypeClassifyNode
from src.nodes.disclosure_req_match_node import DisclosureReqMatchNode
from src.nodes.fiea_corpus_retrieve_node import FIEACorpusRetrieveNode
from src.nodes.template_generate_node import TemplateGenerateNode
from src.schemas.state import State


class AdviceDisclosureWorkflowGraph(BaseGraph):
    """Inner graph for the FIN-C2-116 AI-advice-disclosure regime workflow."""

    @property
    def name(self) -> str:
        return "fin-c2-116-advice-disclosure-workflow"

    @property
    def state_schema(self) -> type:
        return State

    def _validate_config(self) -> None:
        # No mandatory config: kb/requirement_table/llm are optional.
        pass

    def register_nodes(self) -> None:
        # No super() - BaseGraph.register_nodes() is abstract.
        kb = self.config.get("kb")
        requirement_table = self.config.get("requirement_table")
        llm = self.config.get("llm")

        self._nodes["fiea_corpus_retrieve"] = FIEACorpusRetrieveNode(kb=kb)
        self._nodes["advice_type_classify"] = AdviceTypeClassifyNode()
        self._nodes["disclosure_req_match"] = DisclosureReqMatchNode(requirement_table=requirement_table)
        self._nodes["template_generate"] = TemplateGenerateNode(llm=llm)

    def add_edges(self) -> None:
        self._sg.add_edge(START, "fiea_corpus_retrieve")
        self._sg.add_conditional_edges(
            "fiea_corpus_retrieve",
            lambda s: END if self._is_error(s) else "advice_type_classify",
            {"advice_type_classify": "advice_type_classify", END: END},
        )
        self._sg.add_conditional_edges(
            "advice_type_classify",
            lambda s: END if self._is_error(s) else "disclosure_req_match",
            {"disclosure_req_match": "disclosure_req_match", END: END},
        )
        self._sg.add_conditional_edges(
            "disclosure_req_match",
            lambda s: END if self._is_error(s) else "template_generate",
            {"template_generate": "template_generate", END: END},
        )
        self._sg.add_edge("template_generate", END)

    @staticmethod
    def _is_error(state: AgentState) -> bool:
        return state.get("status") in (AgentStatus.ERROR.value, AgentStatus.ERROR.value)

    def route(self, state: AgentState) -> str:
        return END if self._is_error(state) else "advice_type_classify"

    def get_output(self, state: AgentState) -> dict[str, Any]:
        return {
            "retrieved_clauses": state.get("retrieved_clauses"),
            "regime_label": state.get("regime_label"),
            "regime_basis": state.get("regime_basis"),
            "disclosure_requirements": state.get("disclosure_requirements"),
            "output": state.get("disclosure_template"),
            "disclosure_template": state.get("disclosure_template"),
            "status": state.get("status"),
            "trace_id": state.get("trace_id"),
            "correlation_id": state.get("correlation_id"),
            "node_history": state.get("node_history", []),
        }
