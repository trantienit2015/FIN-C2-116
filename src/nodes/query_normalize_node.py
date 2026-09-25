"""AgentCore Platform v1.0 - FIN-C2-116 QueryNormalizeNode (outer pre_process).

Combines InputValidation (S-1 + S-2) + query normalization per the design's
node flow. S-2 domain check is a regex/pattern reject on
credential/JWT/personal-number-shaped tokens - NOT an LLM judgment.
"""

import re
from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

from src.services.service import normalize_query

# Regex/pattern reject for credentials, JWTs, and JP personal-number
# (個人番号, 12 digits) shaped tokens in the raw query - deterministic,
# not an LLM check.
_CREDENTIAL_OR_PII_PATTERN = re.compile(
    r"(sk-[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+|\b\d{4}\s?\d{4}\s?\d{4}\b)"
)


class QueryNormalizeNode(FunctionNode):
    """Validate the compliance question, reject credential/PII-shaped input, normalize."""

    # Outer node - trust must match agent.yaml's agent-level required_trust_level
    # (this agent's boundary: VERIFIED_EXTERNAL, authenticated compliance staff).
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        user_input = state.get("user_input", "")

        if not user_input or not user_input.strip():
            emit_trace_event("query_normalize_blocked", {"reason": "user_input_missing"}, state)
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["QueryNormalizeNode: user_input is empty or missing"],
            }

        if _CREDENTIAL_OR_PII_PATTERN.search(user_input):
            emit_trace_event("query_normalize_blocked", {"reason": "s2_credential_or_pii_reject"}, state)
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": [
                    "QueryNormalizeNode: S-2 reject - credential or personal-number-shaped token detected in input"
                ],
            }

        query_text = normalize_query(user_input)

        # S-4: domain event for the normalized-query dispatch - length only, no raw content.
        emit_trace_event("query_normalized", {"query_length": len(query_text)}, state)

        return {
            "query_text": query_text,
            "validated_input": query_text,
            "status": AgentStatus.SUCCESS.value,
        }
