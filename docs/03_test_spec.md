# Test Specification

## Test Strategy
- Coverage target: all BL paths (unit + integration); hard % threshold enforced by CI gate
- Test types: Unit (`tests/unit/`) / Integration (`tests/integration/`) / Proof-of-Boundary (`tests/proof_of_boundary/`)

## Framework Compliance Tests (Mandatory)

| TC-ID | Test | Expected Result | Result |
|-------|------|----------------|--------|
| TC-01 | State contract: flat TypedDict | Type check pass, no Pydantic/dataclass | PASS |
| TC-02 | Fail-closed validation on empty/invalid input | Error dict returned, no raise | PASS |
| TC-03 | No JWT/Credential in State | CI `gate-credential-scan`: 0 violations | PASS |
| TC-04 | InvocationContext via configurable only | Never present in post-invoke state | PASS |
| TC-05 | S-4: no duplicate lifecycle events in `execute()` | `node_start` / `node_complete` / `node_error` absent from `execute()` body | 0 duplicates |
| TC-06 | S-2: `_security_gate_input()` not overridden (`FunctionNode` subclass) | `TypeError` raised at class definition if overridden | 0 overrides |
| TC-07 | S-3: `_security_gate_output()` not overridden (`FunctionNode` subclass) | `TypeError` raised at class definition if overridden | 0 overrides |
| TC-08 | `required_trust_level` enforced | Insufficient trust → refused | PASS |
| TC-09 | S-2: domain check via QueryNormalizeNode's deterministic regex reject | Credential/personal-number-shaped input rejected | PASS |
| TC-10 | S-3: `_extra_security_gate_output()` on ResponseValidateNode | Unsourced citation / missing disclaimer blocked | PASS |
| TC-11 | S-4: at least one domain `emit_trace_event()` inside each `execute()` | Domain event emitted on every invocation path | ≥1 per node |

## Proof-of-Boundary Tests (Mandatory)

| PB-ID | Boundary | Test | Expected Result | Result |
|-------|----------|------|----------------|--------|
| PB-1 | BaseNode → EventEmitter | `emit_trace_event()` fires on every invocation path | No silent failures | PASS |
| PB-2 | State serialization | Post-invoke State is primitives only | No Pydantic/dataclass | PASS |
| PB-3 | L1 → External service | FIEA/FSA KB lookup (deterministic keyword-match fallback; real deployment = hybrid dense+sparse vector search) | Data retrieved | PASS |
| PB-4 | Import isolation | No Level 0 imports | AST scan: 0 violations | PASS |
| PB-5 | Checkpoint safety | No JWT/Pydantic in checkpoint | Inspection pass | PASS |
| PB-6 | Invoke execution order | `__call__()`: S-1 trust gate → S-4 `node_start` → S-2 `_security_gate_input` → `execute()` → S-3 `_security_gate_output` → S-4 `node_complete` | Order verified | PASS |
| PB-7 | HITL interrupt propagation *(conditional)* | `hitl.enabled` is not set in `config/agent.yaml` | **Auto-waived — non-HITL** | N/A (auto-skip) |

> **Pre-review gate checklist:** PB-1 through PB-6 are mandatory. PB-7 auto-waived (this template has no `interrupt()` call and `hitl.enabled` is absent).

## Business Logic Tests

| TC-ID | Test | Input | Expected Result | Result |
|-------|------|-------|----------------|--------|
| BL-01 | Advice-regime classification | "The AI output says you should buy this fund now" | `regime_label == "advice"`, cited basis clauses present | PASS |
| BL-02 | Information-regime classification | "What is the current NAV of this fund?" | `regime_label == "information"` | PASS |
| BL-03 | Unsourced citation rejected | Answer citing a clause_id never retrieved | ResponseValidateNode returns ERROR (S-3 blocks) | PASS |
| BL-04 | Missing mandatory disclaimer rejected | Answer without the qualified-counsel disclaimer | ResponseValidateNode returns ERROR (S-3 blocks) | PASS |
| BL-05 | Credential/PII-shaped input rejected at entry | Query containing an `sk-...`-shaped token | QueryNormalizeNode returns ERROR (S-2 reject) | PASS |

## Test Execution Summary
- Execution date: 2026-07-17
- Total tests: see CI `run-tests` job (`pytest tests/ -v` + `pytest tests/proof_of_boundary/ -v`)
- Pass / Fail / Skip: tracked per CI pipeline run (PB-7 skip is expected/by-design)
- Coverage: all node success + error/edge paths (unit) + full-graph compile+invoke (integration)
