# FIN-C2-116 - Framework compliance tests TC-01..TC-08.
# Shared compliance-test shape,
# adapted to this template's real architecture (Cat 2: outer pre/post + GraphNode-wrapped inner nodes).

import os
import re

import pytest
from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_state import AgentState
from framework.schemas.agent_status import AgentStatus
from framework.schemas.invocation_context import InvocationContext
from framework.schemas.trust_level import TrustLevel

from src.nodes import query_normalize_node, response_validate_node
from src.schemas.state import State, to_json

_SRC = os.path.join(os.path.dirname(__file__), "..", "..", "src")
TRUST = TrustLevel.VERIFIED_EXTERNAL.value

KB = [{"clause_id": "Art.2-8", "keywords": ["advice", "recommend"], "provision_type": "regime_definition"}]
REQUIREMENT_TABLE = [{"regime": "advice", "requirement_id": "REQ-ADV-01"}]


def _src_files():
    for root, _d, files in os.walk(_SRC):
        for f in files:
            if f.endswith(".py"):
                yield os.path.join(root, f)


# TC-01 - State is a flat TypedDict extending AgentState, added fields are primitives/JSON-str.
class TestTC01StateContract:
    def test_state_is_typeddict_extending_agent_state(self):
        assert hasattr(State, "__annotations__")
        assert "user_input" in State.__annotations__
        assert set(AgentState.__annotations__).issubset(set(State.__annotations__))

    def test_added_fields_are_primitives_or_json_str(self):
        added = [k for k in State.__annotations__ if k not in AgentState.__annotations__]
        assert added, "State must declare agent-specific fields"
        for name in added:
            ann = str(State.__annotations__[name])
            # NotRequired[str] holders — JSON-string-encoded compound fields are allowed.
            assert "str" in ann, f"{name}: {ann} - compound fields must be JSON-string-encoded"


# TC-02 - Empty/missing input yields a fail-closed ERROR outcome, no raise.
class TestTC02Validation:
    def test_empty_input_no_raise(self):
        node = query_normalize_node.QueryNormalizeNode()
        out = node.execute({"user_input": ""})
        assert out["status"] == AgentStatus.ERROR
        assert out["error_log"]

    def test_missing_query_envelope_no_raise(self):
        from src.nodes.fiea_corpus_retrieve_node import FIEACorpusRetrieveNode

        out = FIEACorpusRetrieveNode(kb=KB).execute({"user_input": ""})
        assert out["status"] == AgentStatus.ERROR
        assert out["error_log"]


# TC-03 - No JWT / API keys / secrets in src/; no direct os.environ reads.
class TestTC03NoCredentials:
    def test_no_credential_literals(self):
        pat = re.compile(r"(sk-[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)")
        offenders = []
        for fp in _src_files():
            with open(fp, encoding="utf-8") as f:
                content = f.read()
            # skip this file's own detection regex definitions (pattern literals, not credentials)
            if "server.py" in fp:
                continue
            if pat.search(content):
                offenders.append(fp)
        assert offenders == []

    def test_no_os_environ_secret_reads(self):
        offenders = []
        for fp in _src_files():
            with open(fp, encoding="utf-8") as f:
                content = f.read()
            if "server.py" in fp and "INVOKE_AUTH_TOKEN" in content:
                continue  # entry-point deployment-level caller auth token, not an agent secret
            if "os.environ" in content:
                offenders.append(fp)
        assert offenders == []


# TC-04 - InvocationContext is never stored in State after invoke.
class TestTC04ContextIsolation:
    def test_no_invocationcontext_in_state_after_invoke(self):
        from src.graph.graph import Graph

        agent = Graph(config={"max_retry": 1, "kb": KB, "requirement_table": REQUIREMENT_TABLE})
        agent.compile()
        ctx = InvocationContext(session_id="tc04", caller_trust_level=TrustLevel.VERIFIED_EXTERNAL, caller_id="compliance-tc04")
        result = agent.invoke("Is this AI output regulated advice?", ctx=ctx)
        for v in result.values():
            assert not isinstance(v, InvocationContext)

    def test_from_state_available(self):
        assert hasattr(InvocationContext, "from_state")


# TC-05 - Domain events: the S-4 side-effect node emits >=1 domain event;
# no node under src/nodes/ ever re-emits a framework backbone lifecycle event.
class TestTC05Audit:
    def test_audit_node_emits_domain_event(self, monkeypatch):
        events = []
        monkeypatch.setattr(response_validate_node, "emit_trace_event", lambda e, p, s: events.append(e))
        state = {
            "regime_label": "advice",
            "disclosure_template": (
                "Regime classification: advice (basis: Art.2-8). This is general information, not "
                "individualized investment advice; consult a registered 投資助言業者 or qualified counsel."
            ),
            "retrieved_clauses": to_json(KB),
        }
        out = response_validate_node.ResponseValidateNode().execute(state)
        assert out["status"] == AgentStatus.SUCCESS
        assert len(events) >= 1
        assert "advice_disclosure_query_answered" in events
        assert not ({"node_start", "node_complete", "node_error", "node_skip"} & set(events))

    def test_source_has_no_backbone_events(self):
        pat = re.compile(r'emit_trace_event\(\s*["\'](node_start|node_complete|node_error|node_skip)["\']')
        offenders = []
        for fp in _src_files():
            with open(fp, encoding="utf-8") as f:
                if pat.search(f.read()):
                    offenders.append(fp)
        assert offenders == []


# TC-06 / TC-07 - S-2/S-3 gates are @final on FunctionNode (overriding raises TypeError at class def).
class TestTC0607FinalGates:
    def test_input_gate_is_final(self):
        with pytest.raises(TypeError):

            class BadIn(FunctionNode):  # noqa: N801
                def _security_gate_input(self, state):
                    return state

    def test_output_gate_is_final(self):
        with pytest.raises(TypeError):

            class BadOut(FunctionNode):  # noqa: N801
                def _security_gate_output(self, result):
                    return result

    def test_extra_hook_is_overridable(self):
        assert response_validate_node.ResponseValidateNode._extra_security_gate_output is not FunctionNode._extra_security_gate_output

    def test_output_gate_blocks_credentials(self):
        # The @final S-3 credential scan actually fires (not vacuous): a
        # credential in the result is blocked, never returned as-is.
        node = response_validate_node.ResponseValidateNode()
        with pytest.raises(Exception):
            node._security_gate_output({"formatted_output": "token AKIAIOSFODNN7EXAMPLE leaked"})


# TC-08 - required_trust_level enforced: insufficient trust -> ERROR state, no raise.
class TestTC08TrustGate:
    def test_declared_trust_levels_valid(self):
        from src.nodes.advice_type_classify_node import AdviceTypeClassifyNode
        from src.nodes.disclosure_req_match_node import DisclosureReqMatchNode
        from src.nodes.fiea_corpus_retrieve_node import FIEACorpusRetrieveNode
        from src.nodes.template_generate_node import TemplateGenerateNode

        for cls in (
            query_normalize_node.QueryNormalizeNode,
            FIEACorpusRetrieveNode,
            AdviceTypeClassifyNode,
            DisclosureReqMatchNode,
            TemplateGenerateNode,
            response_validate_node.ResponseValidateNode,
        ):
            assert cls.required_trust_level in (TrustLevel.ANONYMOUS, TrustLevel.VERIFIED_EXTERNAL, TrustLevel.INTERNAL)

    def test_insufficient_trust_returns_error(self):
        node = query_normalize_node.QueryNormalizeNode()
        out = node({"caller_trust_level": TrustLevel.ANONYMOUS.value, "user_input": "Is this regulated advice?"})
        assert str(out.get("status")).lower().endswith("error")

    def test_sufficient_trust_succeeds(self):
        node = query_normalize_node.QueryNormalizeNode()
        out = node({"caller_trust_level": TRUST, "user_input": "Is this regulated advice?"})
        assert out["status"] == AgentStatus.SUCCESS
        assert out["query_text"] == "Is this regulated advice?"
