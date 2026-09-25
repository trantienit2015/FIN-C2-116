# FIN-C2-116 - LLM contract for TemplateGenerateNode / generate_disclosure_template.
#
# Canonical BaseLLM.complete(messages: list) -> dict ({"content": str, ...}).
# A configured-but-failing/empty/malformed LLM must surface as
# AgentStatus.ERROR.value, never a silently-degraded SUCCESS - the
# deterministic fallback template is reserved for llm=None (no LLM
# configured at all).

from framework.schemas.agent_status import AgentStatus

from src.nodes.template_generate_node import TemplateGenerateNode
from src.schemas.state import to_json
from src.services.service import LLMGenerationError, generate_disclosure_template

REGIME_LABEL = "advice"
REQUIREMENTS = [{"regime": "advice", "requirement_id": "REQ-ADV-01"}]
RETRIEVED_CLAUSES = [{"clause_id": "Art.2-8"}]


class DictLLM:
    """Canonical BaseLLM.complete() shape - a real production client."""

    def complete(self, messages):
        assert isinstance(messages, list)
        return {"content": "Regime classification: advice, citing Art.2-8.", "model": "mock"}


class EmptyLLM:
    """Configured LLM that returns unusable (empty) content."""

    def complete(self, messages):
        return {"content": ""}


class RaisingLLM:
    """Configured LLM whose provider call fails (timeout/transport)."""

    def complete(self, messages):
        raise RuntimeError("provider timeout")


class BareStringLLM:
    """Backward-compat fake that returns a bare string (not the canonical dict)."""

    def complete(self, messages):
        return "Regime classification: advice."


class TestGenerateDisclosureTemplateService:
    def test_dict_llm_normalizes_content(self):
        template = generate_disclosure_template(REGIME_LABEL, REQUIREMENTS, RETRIEVED_CLAUSES, llm=DictLLM())
        assert isinstance(template, str)
        assert "Regime classification: advice" in template

    def test_bare_string_llm_backward_compat(self):
        template = generate_disclosure_template(REGIME_LABEL, REQUIREMENTS, RETRIEVED_CLAUSES, llm=BareStringLLM())
        assert isinstance(template, str)
        assert "Regime classification: advice." in template

    def test_empty_llm_content_raises(self):
        try:
            generate_disclosure_template(REGIME_LABEL, REQUIREMENTS, RETRIEVED_CLAUSES, llm=EmptyLLM())
            raise AssertionError("expected LLMGenerationError")
        except LLMGenerationError:
            pass

    def test_raising_llm_raises_generation_error(self):
        try:
            generate_disclosure_template(REGIME_LABEL, REQUIREMENTS, RETRIEVED_CLAUSES, llm=RaisingLLM())
            raise AssertionError("expected LLMGenerationError")
        except LLMGenerationError:
            pass

    def test_llm_none_uses_deterministic_fallback(self):
        template = generate_disclosure_template(REGIME_LABEL, REQUIREMENTS, RETRIEVED_CLAUSES, llm=None)
        assert isinstance(template, str)
        assert "Regime classification: advice" in template


class TestTemplateGenerateNodeLLMContract:
    def _state(self):
        return {
            "regime_label": REGIME_LABEL,
            "disclosure_requirements": to_json(REQUIREMENTS),
            "retrieved_clauses": to_json(RETRIEVED_CLAUSES),
        }

    def test_configured_llm_success(self):
        r = TemplateGenerateNode(llm=DictLLM()).execute(self._state())
        assert r["status"] == AgentStatus.SUCCESS.value
        assert isinstance(r["disclosure_template"], str)

    def test_configured_llm_empty_content_is_error_not_fallback(self):
        r = TemplateGenerateNode(llm=EmptyLLM()).execute(self._state())
        assert r["status"] == AgentStatus.ERROR.value
        assert "disclosure_template" not in r

    def test_configured_llm_provider_failure_is_error_not_fallback(self):
        r = TemplateGenerateNode(llm=RaisingLLM()).execute(self._state())
        assert r["status"] == AgentStatus.ERROR.value
        assert "disclosure_template" not in r

    def test_no_llm_configured_uses_deterministic_fallback_success(self):
        r = TemplateGenerateNode(llm=None).execute(self._state())
        assert r["status"] == AgentStatus.SUCCESS.value
        assert isinstance(r["disclosure_template"], str)
