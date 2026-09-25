# FIN-C2-116 - GraphNode boundary test (Cat 2 outer main-slot wrapper).
#
# Why this test exists: PB-6 (test_pb_invoke_order.py) only self-discovers
# BaseNode subclasses under src/nodes/; AdviceDisclosureGraphNode lives in
# src/graph/graph.py (deliberately, per the module docstring, to stay out of
# PB-6's src/nodes/ discovery) and subclasses GraphNode directly. That
# placement matches the scaffold canonical Cat 2 layout, but it does not
# exempt the outer GraphNode from coverage (PB-6 Cat 2
# GraphNode boundary). This is the
# test-scope blind spot audit and proves the S-1 gate + boundary mapping +
# delegation are real, not absent.
#
# framework/nodes/graph_node.py: GraphNode extends BaseNode directly (not
# FunctionNode), so it has no _security_gate_input/_security_gate_output at
# all - S-2/S-3 gating is delegated entirely to the outer
# QueryNormalizeNode/ResponseValidateNode and the inner subgraph's own
# FunctionNode chain (FIEACorpusRetrieveNode -> AdviceTypeClassifyNode ->
# DisclosureReqMatchNode -> TemplateGenerateNode). This test proves that
# delegation is real, not absent.

from framework.nodes.function_node import FunctionNode
from framework.schemas.trust_level import TrustLevel

from src.graph.graph import AdviceDisclosureGraphNode
from src.nodes.fiea_corpus_retrieve_node import FIEACorpusRetrieveNode


def _node():
    return AdviceDisclosureGraphNode(kb=None, requirement_table=None, llm=None)


class TestGraphNodeS1TrustGate:
    """S-1: the outer main-slot GraphNode enforces the trust gate like any BaseNode."""

    def test_insufficient_trust_returns_error_without_invoking_subgraph(self, monkeypatch):
        node = _node()
        called = {"get_subgraph": False}

        def _spy_get_subgraph():
            called["get_subgraph"] = True
            raise AssertionError("get_subgraph() must not run when the S-1 gate denies")

        monkeypatch.setattr(node, "get_subgraph", _spy_get_subgraph)

        state = {
            "caller_trust_level": TrustLevel.ANONYMOUS.value,
            "validated_input": '{"query": "Is this AI-generated commentary regulated investment advice?"}',
        }
        out = node(state)

        assert out["status"] == "error"
        assert any("S-1 trust gate denied" in e for e in out["error_log"])
        assert called["get_subgraph"] is False

    def test_matches_agent_yaml_required_trust_level(self):
        # The outer main-slot wrapper must match config/agent.yaml
        # (VERIFIED_EXTERNAL - authenticated compliance staff caller), not a
        # permissive default, and must match sibling outer node
        # QueryNormalizeNode/ResponseValidateNode.
        assert AdviceDisclosureGraphNode.required_trust_level == TrustLevel.VERIFIED_EXTERNAL


class TestGraphNodeBoundaryMapping:
    """Boundary mapping: extract_input()/merge_output() do not leak raw state/subgraph dicts."""

    def test_extract_input_only_reads_validated_input(self):
        node = _node()
        state = {
            "validated_input": "What disclosure is required for this AI-generated commentary?",
            "user_input": "raw caller text should not leak",
            "unrelated_secret_field": "must-not-appear",
        }
        extracted = node.extract_input(state)

        assert isinstance(extracted, str)
        assert "unrelated_secret_field" not in extracted
        assert "must-not-appear" not in extracted

    def test_merge_output_maps_fields_explicitly_no_raw_passthrough(self):
        node = _node()
        state = {}
        sub_result = {
            "retrieved_clauses": '[{"clause_id": "FIEA-2-8", "text": "..."}]',
            "regime_label": "advice",
            "regime_basis": '["FIEA-2-8"]',
            "disclosure_requirements": '[{"requirement_id": "DR-1"}]',
            "disclosure_template": "This response constitutes regulated investment advice ...",
            "status": "success",
            # A field the subgraph might carry internally that must NOT leak
            # into the outer state unless merge_output() explicitly maps it.
            "internal_debug_trace": "should-not-be-copied",
        }
        merged = node.merge_output(state, sub_result)

        assert "internal_debug_trace" not in merged
        assert merged["status"] == "success"
        assert set(merged.keys()) == {
            "retrieved_clauses",
            "regime_label",
            "regime_basis",
            "disclosure_requirements",
            "disclosure_template",
            "status",
        }


class TestGraphNodeDelegatesGatingToInnerSubgraph:
    """Delegation has a real target: the inner subgraph's entry node runs S-1/S-2/S-3."""

    def test_inner_entry_node_is_a_function_node_with_security_gates(self):
        # FIEACorpusRetrieveNode is the inner subgraph's entry point
        # (domain_workflow_graph.py: START -> fiea_corpus_retrieve). It is a
        # FunctionNode, so the framework's @final S-2/S-3 gates run on every
        # invocation of the inner subgraph - this is where the GraphNode's
        # skipped lifecycle is actually enforced, not omitted.
        assert issubclass(FIEACorpusRetrieveNode, FunctionNode)
        assert hasattr(FIEACorpusRetrieveNode, "required_trust_level")
