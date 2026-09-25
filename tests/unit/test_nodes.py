# FIN-C2-116 - Unit tests: per-node success + error/edge paths.

from framework.schemas.agent_status import AgentStatus

from src.nodes.advice_type_classify_node import AdviceTypeClassifyNode
from src.nodes.disclosure_req_match_node import DisclosureReqMatchNode
from src.nodes.fiea_corpus_retrieve_node import FIEACorpusRetrieveNode
from src.nodes.query_normalize_node import QueryNormalizeNode
from src.nodes.response_validate_node import ResponseValidateNode
from src.nodes.template_generate_node import TemplateGenerateNode
from src.schemas.state import from_json, to_json

KB = [
    {"clause_id": "Art.2-8", "keywords": ["advice", "recommend"], "provision_type": "regime_definition"},
    {"clause_id": "FSA-2026-14", "keywords": ["disclosure", "registration"], "provision_type": "disclosure"},
]
REQUIREMENT_TABLE = [
    {"regime": "advice", "requirement_id": "REQ-ADV-01"},
    {"regime": "information", "requirement_id": "REQ-INFO-01"},
]
MANDATORY_DISCLAIMER = "This is general information, not individualized investment advice; consult a registered 投資助言業者 or qualified counsel."


class TestQueryNormalizeNode:
    def test_success(self):
        state = {"user_input": "  Is this AI recommendation regulated advice?  "}
        r = QueryNormalizeNode().execute(state)
        assert r["status"] == AgentStatus.SUCCESS
        assert r["query_text"] == "Is this AI recommendation regulated advice?"

    def test_empty_input_error(self):
        assert QueryNormalizeNode().execute({"user_input": ""})["status"] == AgentStatus.ERROR

    def test_credential_shaped_input_rejected(self):
        state = {"user_input": "here is my token sk-abcdefghijklmnopqrstuvwx please classify"}
        r = QueryNormalizeNode().execute(state)
        assert r["status"] == AgentStatus.ERROR
        assert "S-2" in r["error_log"][0]


class TestFIEACorpusRetrieveNode:
    def test_success_matches_found(self):
        envelope = {"query": "Does this AI output recommend a specific investment?"}
        state = {"user_input": to_json(envelope)}
        r = FIEACorpusRetrieveNode(kb=KB).execute(state)
        assert r["status"] == AgentStatus.SUCCESS
        assert len(from_json(r["retrieved_clauses"], [])) >= 1

    def test_missing_query_error(self):
        assert FIEACorpusRetrieveNode(kb=KB).execute({"user_input": ""})["status"] == AgentStatus.ERROR


class TestAdviceTypeClassifyNode:
    def test_success_advice_regime(self):
        envelope = {"query": "The AI output says you should buy this fund now."}
        state = {"user_input": to_json(envelope), "retrieved_clauses": to_json(KB)}
        r = AdviceTypeClassifyNode().execute(state)
        assert r["status"] == AgentStatus.SUCCESS
        assert r["regime_label"] == "advice"
        assert len(from_json(r["regime_basis"], [])) == len(KB)

    def test_success_information_regime(self):
        envelope = {"query": "What is the current NAV of this fund?"}
        state = {"user_input": to_json(envelope), "retrieved_clauses": to_json(KB)}
        r = AdviceTypeClassifyNode().execute(state)
        assert r["status"] == AgentStatus.SUCCESS
        assert r["regime_label"] == "information"

    def test_no_retrieved_clauses_error(self):
        envelope = {"query": "any question"}
        state = {"user_input": to_json(envelope), "retrieved_clauses": to_json([])}
        assert AdviceTypeClassifyNode().execute(state)["status"] == AgentStatus.ERROR

    def test_missing_query_error(self):
        state = {"user_input": to_json({}), "retrieved_clauses": to_json(KB)}
        assert AdviceTypeClassifyNode().execute(state)["status"] == AgentStatus.ERROR


class TestDisclosureReqMatchNode:
    def test_success(self):
        state = {"regime_label": "advice"}
        r = DisclosureReqMatchNode(requirement_table=REQUIREMENT_TABLE).execute(state)
        assert r["status"] == AgentStatus.SUCCESS
        assert len(from_json(r["disclosure_requirements"], [])) == 1

    def test_missing_regime_error(self):
        assert DisclosureReqMatchNode(requirement_table=REQUIREMENT_TABLE).execute({})["status"] == AgentStatus.ERROR


class TestTemplateGenerateNode:
    def test_success(self):
        state = {
            "regime_label": "advice",
            "disclosure_requirements": to_json([{"regime": "advice", "requirement_id": "REQ-ADV-01"}]),
            "retrieved_clauses": to_json(KB),
        }
        r = TemplateGenerateNode().execute(state)
        assert r["status"] == AgentStatus.SUCCESS
        assert MANDATORY_DISCLAIMER in r["disclosure_template"]

    def test_missing_regime_error(self):
        assert TemplateGenerateNode().execute({})["status"] == AgentStatus.ERROR


class TestResponseValidateNode:
    def test_success_all_sourced(self):
        state = {
            "regime_label": "advice",
            "disclosure_template": f"Regime classification: advice (basis: Art.2-8). {MANDATORY_DISCLAIMER}",
            "retrieved_clauses": to_json(KB),
        }
        r = ResponseValidateNode().execute(state)
        assert r["status"] == AgentStatus.SUCCESS
        assert r["validated_answer"]

    def test_unsourced_citation_error(self):
        state = {
            "regime_label": "advice",
            "disclosure_template": f"Cites Art.99-9 which was never retrieved. {MANDATORY_DISCLAIMER}",
            "retrieved_clauses": to_json(KB),
        }
        assert ResponseValidateNode().execute(state)["status"] == AgentStatus.ERROR

    def test_missing_disclaimer_error(self):
        state = {
            "regime_label": "advice",
            "disclosure_template": "Regime classification: advice (basis: Art.2-8).",
            "retrieved_clauses": to_json(KB),
        }
        assert ResponseValidateNode().execute(state)["status"] == AgentStatus.ERROR

    def test_extra_gate_blocks_unsourced_reference(self):
        bad_state = {"disclosure_template": "Cites Art.99-9 fabricated.", "retrieved_clauses": to_json(KB)}
        out = ResponseValidateNode()._extra_security_gate_output(bad_state)
        assert out["status"] == AgentStatus.ERROR

    def test_extra_gate_passthrough_valid_answer(self):
        good_state = {
            "disclosure_template": f"Regime classification: advice (basis: Art.2-8). {MANDATORY_DISCLAIMER}",
            "retrieved_clauses": to_json(KB),
        }
        assert ResponseValidateNode()._extra_security_gate_output(good_state) is good_state

    def test_extra_gate_passes_execute_output_alone(self):
        # The framework hands the S-3 hook only the dict execute() returned, not the
        # accumulated state; the success output must therefore pass the hook on its own.
        state = {
            "regime_label": "advice",
            "disclosure_template": f"Regime classification: advice (basis: Art.2-8). {MANDATORY_DISCLAIMER}",
            "retrieved_clauses": to_json(KB),
        }
        node = ResponseValidateNode()
        out = node.execute(state)
        assert out["status"] == AgentStatus.SUCCESS.value
        assert node._extra_security_gate_output(out) is out

    def test_extra_gate_keeps_execute_error(self):
        node = ResponseValidateNode()
        out = node.execute({"disclosure_template": "no disclaimer", "retrieved_clauses": to_json(KB)})
        assert out["status"] == AgentStatus.ERROR.value
        assert node._extra_security_gate_output(out) is out
