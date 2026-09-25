# FIN-C2-116 - S-4 audit coverage: emit_trace_event() fires on every execute()
# path (success + every early-return reject), not only the success tail.
# Monkeypatch targets the symbol *inside each node module* (each node does
# `from shared.utils.audit_logger import emit_trace_event`, so patching
# shared.utils.audit_logger does not affect the already-bound name).

from framework.schemas.agent_status import AgentStatus

import src.nodes.advice_type_classify_node as advice_type_classify_node
import src.nodes.disclosure_req_match_node as disclosure_req_match_node
import src.nodes.fiea_corpus_retrieve_node as fiea_corpus_retrieve_node
import src.nodes.query_normalize_node as query_normalize_node
import src.nodes.response_validate_node as response_validate_node
import src.nodes.template_generate_node as template_generate_node
from src.schemas.state import to_json

KB = [
    {"clause_id": "Art.2-8", "keywords": ["advice", "recommend"], "provision_type": "regime_definition"},
]
REQUIREMENT_TABLE = [{"regime": "advice", "requirement_id": "REQ-ADV-01"}]
MANDATORY_DISCLAIMER = "This is general information, not individualized investment advice; consult a registered 投資助言業者 or qualified counsel."

# Values that must never appear in a recorded event payload.
_NON_SENSITIVE_GUARD_TERMS = ("sk-abcdefghijklmnopqrstuvwx", "1234 5678 9012")


def _capture(monkeypatch, module):
    events = []
    monkeypatch.setattr(module, "emit_trace_event", lambda name, payload, state: events.append((name, payload)))
    return events


def _assert_non_sensitive(events):
    for _name, payload in events:
        for value in payload.values():
            text = str(value)
            for term in _NON_SENSITIVE_GUARD_TERMS:
                assert term not in text


class TestQueryNormalizeNodeEmits:
    def test_success_emits(self, monkeypatch):
        events = _capture(monkeypatch, query_normalize_node)
        r = query_normalize_node.QueryNormalizeNode().execute({"user_input": "Is this regulated advice?"})
        assert r["status"] == AgentStatus.SUCCESS.value
        assert events and events[0][0] == "query_normalized"
        _assert_non_sensitive(events)

    def test_empty_input_emits_blocked(self, monkeypatch):
        events = _capture(monkeypatch, query_normalize_node)
        query_normalize_node.QueryNormalizeNode().execute({"user_input": ""})
        assert events and events[0][0] == "query_normalize_blocked"
        _assert_non_sensitive(events)

    def test_credential_reject_emits_blocked_without_leaking_token(self, monkeypatch):
        events = _capture(monkeypatch, query_normalize_node)
        query_normalize_node.QueryNormalizeNode().execute(
            {"user_input": "here is my token sk-abcdefghijklmnopqrstuvwx please classify"}
        )
        assert events and events[0][0] == "query_normalize_blocked"
        _assert_non_sensitive(events)


class TestFIEACorpusRetrieveNodeEmits:
    def test_success_emits(self, monkeypatch):
        events = _capture(monkeypatch, fiea_corpus_retrieve_node)
        state = {"user_input": to_json({"query": "Does this recommend a specific fund?"})}
        r = fiea_corpus_retrieve_node.FIEACorpusRetrieveNode(kb=KB).execute(state)
        assert r["status"] == AgentStatus.SUCCESS.value
        assert events and events[0][0] == "fiea_clauses_retrieved"

    def test_missing_query_emits_blocked(self, monkeypatch):
        events = _capture(monkeypatch, fiea_corpus_retrieve_node)
        fiea_corpus_retrieve_node.FIEACorpusRetrieveNode(kb=KB).execute({"user_input": ""})
        assert events and events[0][0] == "fiea_clauses_retrieve_blocked"


class TestAdviceTypeClassifyNodeEmits:
    def test_success_emits(self, monkeypatch):
        events = _capture(monkeypatch, advice_type_classify_node)
        envelope = to_json({"query": "You should buy this fund now."})
        state = {"user_input": envelope, "retrieved_clauses": to_json(KB)}
        r = advice_type_classify_node.AdviceTypeClassifyNode().execute(state)
        assert r["status"] == AgentStatus.SUCCESS.value
        assert events and events[0][0] == "advice_regime_classified"

    def test_missing_query_emits_blocked(self, monkeypatch):
        events = _capture(monkeypatch, advice_type_classify_node)
        state = {"user_input": to_json({}), "retrieved_clauses": to_json(KB)}
        advice_type_classify_node.AdviceTypeClassifyNode().execute(state)
        assert events and events[0][0] == "advice_regime_classify_blocked"

    def test_no_retrieved_clauses_emits_blocked(self, monkeypatch):
        events = _capture(monkeypatch, advice_type_classify_node)
        state = {"user_input": to_json({"query": "any"}), "retrieved_clauses": to_json([])}
        advice_type_classify_node.AdviceTypeClassifyNode().execute(state)
        assert events and events[0][0] == "advice_regime_classify_blocked"


class TestDisclosureReqMatchNodeEmits:
    def test_success_emits(self, monkeypatch):
        events = _capture(monkeypatch, disclosure_req_match_node)
        r = disclosure_req_match_node.DisclosureReqMatchNode(requirement_table=REQUIREMENT_TABLE).execute(
            {"regime_label": "advice"}
        )
        assert r["status"] == AgentStatus.SUCCESS.value
        assert events and events[0][0] == "disclosure_requirements_matched"

    def test_missing_regime_emits_blocked(self, monkeypatch):
        events = _capture(monkeypatch, disclosure_req_match_node)
        disclosure_req_match_node.DisclosureReqMatchNode(requirement_table=REQUIREMENT_TABLE).execute({})
        assert events and events[0][0] == "disclosure_requirements_match_blocked"


class TestTemplateGenerateNodeEmits:
    def test_success_emits(self, monkeypatch):
        events = _capture(monkeypatch, template_generate_node)
        state = {
            "regime_label": "advice",
            "disclosure_requirements": to_json(REQUIREMENT_TABLE),
            "retrieved_clauses": to_json(KB),
        }
        r = template_generate_node.TemplateGenerateNode().execute(state)
        assert r["status"] == AgentStatus.SUCCESS.value
        assert events and events[0][0] == "disclosure_template_generated"

    def test_missing_regime_emits_blocked(self, monkeypatch):
        events = _capture(monkeypatch, template_generate_node)
        template_generate_node.TemplateGenerateNode().execute({})
        assert events and events[0][0] == "disclosure_template_generate_blocked"


class TestResponseValidateNodeEmits:
    def test_success_emits(self, monkeypatch):
        events = _capture(monkeypatch, response_validate_node)
        state = {
            "regime_label": "advice",
            "disclosure_template": f"Regime classification: advice (basis: Art.2-8). {MANDATORY_DISCLAIMER}",
            "retrieved_clauses": to_json(KB),
        }
        r = response_validate_node.ResponseValidateNode().execute(state)
        assert r["status"] == AgentStatus.SUCCESS.value
        assert events and events[0][0] == "advice_disclosure_query_answered"

    def test_unsourced_citation_emits_blocked(self, monkeypatch):
        events = _capture(monkeypatch, response_validate_node)
        state = {
            "regime_label": "advice",
            "disclosure_template": f"Cites Art.99-9 which was never retrieved. {MANDATORY_DISCLAIMER}",
            "retrieved_clauses": to_json(KB),
        }
        response_validate_node.ResponseValidateNode().execute(state)
        assert events and events[0][0] == "response_validate_blocked"

    def test_missing_disclaimer_emits_blocked(self, monkeypatch):
        events = _capture(monkeypatch, response_validate_node)
        state = {
            "regime_label": "advice",
            "disclosure_template": "Regime classification: advice (basis: Art.2-8).",
            "retrieved_clauses": to_json(KB),
        }
        response_validate_node.ResponseValidateNode().execute(state)
        assert events and events[0][0] == "response_validate_blocked"
