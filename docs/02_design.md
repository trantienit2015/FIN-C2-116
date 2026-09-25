# Template Design Specification

## Position in AgentCore Architecture

- **Agent Class**: FINAIAdviceDisclosureAgent
- **L1 Base**: AgentBaseGraph (outer) — Cat 2 composition with `GraphNode`-wrapped inner `BaseGraph`
- **Three-Layer Separation**:
  - State: flat TypedDict composition (no Pydantic — msgpack incompatible)
  - Node: L1 inheritance (Template Method: `execute(self, state: dict) -> dict` override only)
  - Graph: composition (`register_nodes()` for node substitution)

## Architecture Overview

Cat 2: outer `AgentBaseGraph` (fixed 5-node backbone) with domain complexity
encapsulated in `AdviceDisclosureGraphNode` (the `main` slot), wrapping an inner
`BaseGraph` (`AdviceDisclosureWorkflowGraph`) that runs the 4 core business steps.

### Node Configuration (outer)

| Node | Responsibility | Input State | Output State | Inherits/Overrides |
|------|---------------|-------------|--------------|-------------------|
| initialize | schema_version, session_id, trust_level | — | — | InitializeNode (default) |
| pre_process | QueryNormalize — S-1/S-2, normalize query, reject credential/PII-shaped input | `user_input` | `query_text`, `validated_input` | `FunctionNode` |
| main | AdviceDisclosureGraphNode — dispatch to inner subgraph | `validated_input` | `retrieved_clauses`, `regime_label`, `regime_basis`, `disclosure_requirements`, `disclosure_template` | `GraphNode` |
| post_process | ResponseValidate — S-3 deterministic clause-grounding + disclaimer gate | `disclosure_template`, `retrieved_clauses` | `validated_answer`, `formatted_output` | `FunctionNode` |
| finalize | response_metadata, total_time_ms | — | — | FinalizeNode (default) |

### Node Configuration (inner — `AdviceDisclosureWorkflowGraph`)

| Node | Responsibility | Input | Output |
|------|---------------|-------|--------|
| fiea_corpus_retrieve (FIEACorpusRetrieve) | Hybrid-style KB lookup over 金商法 2026 AI-disclosure KB | `{query}` envelope | `retrieved_clauses` |
| advice_type_classify (AdviceTypeClassify) | CRITICAL regime gate: advice vs information, grounded in retrieved clauses | `retrieved_clauses` | `regime_label`, `regime_basis` |
| disclosure_req_match (DisclosureReqMatch) | Match regime to disclosure requirement set | `regime_label` | `disclosure_requirements` |
| template_generate (TemplateGenerate) | Generate citation-grounded disclosure template | `disclosure_requirements`, `retrieved_clauses` | `disclosure_template` |

### Data Flow

```
START → initialize → pre_process(QueryNormalize) → main(GraphNode)
      → post_process(ResponseValidate) → finalize → END
                                    │
                                    ▼ (main slot dispatches to inner subgraph)
        INNER: START → fiea_corpus_retrieve → advice_type_classify
             → disclosure_req_match → template_generate → END
```

### State Definition

| Field | Type | Purpose | Required |
|-------|------|---------|----------|
| query_text | NotRequired[str] | Normalized staff/compliance-officer question | No |
| retrieved_clauses | NotRequired[str] (JSON) | Matched FIEA/FSA KB clauses (clause_id, text, score) | No |
| regime_label | NotRequired[str] | "advice" \| "information" classification | No |
| regime_basis | NotRequired[str] (JSON) | Clause IDs the classification is grounded in | No |
| disclosure_requirements | NotRequired[str] (JSON) | Matched disclosure requirement entries | No |
| disclosure_template | NotRequired[str] | Generated disclosure-wording template | No |
| validated_answer | NotRequired[str] | Final S-3-validated answer | No |

**State Constraints (mandatory):**
- Flat TypedDict only (primitives + JSON-serializable types)
- No JWT, API keys, credentials in State (checkpoint DB leakage)
- InvocationContext via `config["configurable"]` only (not in State)
- No Pydantic models, dataclass, arbitrary Python objects (msgpack incompatible)

## Framework Utilization

### Shared Components Used
- [x] InvocationContext (correlation_id, session_id, permissions, credential handle)
- [x] ConnectionPolicy (retry/timeout strategy — `max_retry: 3`, `timeout_seconds: 30`)
- [ ] SecurityViolationError (not raised directly — S-2 reject returns an ERROR dict instead)
- [x] S-2: `_extra_security_gate_input()` — not needed; QueryNormalizeNode's `execute()` already
      performs the deterministic credential/personal-number regex reject before the framework's
      default PII scan runs.
- [x] S-3: `_extra_security_gate_output()` — implemented on `ResponseValidateNode`: non-suppressible
      re-check that every clause citation in the answer exists in `retrieved_clauses`, and the
      mandatory qualified-counsel disclaimer is present (fabricated-citation + missing-disclaimer
      both block the output).
- [x] S-4: `emit_trace_event()` — every node emits ≥1 domain event inside `execute()`
      (`query_normalized`, `fiea_clauses_retrieved`, `advice_regime_classified`,
      `disclosure_requirements_matched`, `disclosure_template_generated`,
      `advice_disclosure_query_answered`), plus the `GraphNode` dispatch/completion events
      (`advice_disclosure_workflow_dispatched` / `_completed`).

> **S-2/S-3 gate behaviour by node type (ADR-017):**
> - `FunctionNode` subclass → framework `@final` gate always runs automatically;
>   extend via `_extra_security_gate_input()` / `_extra_security_gate_output()` only
> - `GraphNode` / `RemoteAgentNode` → deliberate no-op (upstream or remote node's gate already applied)
> - Custom `BaseNode` subclass → must implement `_security_gate_input()` and
>   `_security_gate_output()` directly (`@abstractmethod` — omission raises `TypeError` at instantiation)

### Composition Pattern

- **Pattern**: GraphNode (subgraph) — outer `AgentBaseGraph` + `AdviceDisclosureGraphNode` (main slot)
  wrapping inner `BaseGraph` (`AdviceDisclosureWorkflowGraph`)
- **Composition target**: `src/graph/domain_workflow_graph.py` (`AdviceDisclosureWorkflowGraph`)
- **Error propagation strategy**: propagate (fail-fast — inner errors surface as `SubgraphError`)

## Import Isolation Confirmation
- [x] Template does not import agenticstar-platform SDK (Level 0)
- [x] Import targets: framework/ and shared/ only (no agents/base/ required)

## Design Decision Record

| Decision | Option A | Option B | Chosen | Rationale |
|----------|----------|----------|--------|-----------|
| L1 base type | AgentBaseGraph | AutonomousBaseGraph | AgentBaseGraph | Fixed multi-step pipeline, no autonomous loop needed |
| Composition pattern | Flat (Cat 1 style) | GraphNode + inner subgraph | GraphNode + inner subgraph | Cat 2 mandate — 4 core business steps live in the inner subgraph, not a single flat MainNode |
