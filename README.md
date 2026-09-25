# FIN-C2-116 — Retail Investor AI Investment Advice Disclosure & FIEA Compliance Q&A Agent

> **Category**: Cat 2 (orchestrates multiple steps to accomplish a specific use case)
> **Industry**: FIN

## Overview

Answers a compliance question about an AI-generated investment output: does it count as
individualized investment advice (which under Japan's Financial Instruments and Exchange Act
requires registration as an investment adviser) or as general information, and which disclosure
requirements apply? The input is the question as plain text. Empty input is rejected, and so is
input containing credential-shaped tokens (API keys, AWS keys, JWTs) or a 12-digit
personal-number-shaped value. The entry nodes require a verified external caller.

The question is normalised and passed to an inner workflow. It first retrieves clauses from a
clause corpus by keyword match (the corpus is supplied as `kb` in `config/config.yaml`; the bundled
entries are illustrative samples, not a legal corpus). If no clause matches, the run ends with an
error rather than classifying without grounding. The regime is then decided by a fixed keyword
heuristic (phrases such as "should buy", "recommend" or 推奨します mean advice, anything else means
information), and matching disclosure requirements are looked up in `requirement_table` from the
same configuration file. Finally a disclosure template is produced that cites the retrieved clause
IDs and the matched requirement IDs, followed by a fixed disclaimer that the text is general
information and not individualized advice. A last step blocks any answer that cites a clause that
was not retrieved or that lacks the disclaimer.

A language model is optional. When a client is supplied through the graph configuration it drafts
the template text instead of the fixed sentence; a failed or empty reply ends the run with an
error. The bundled HTTP entry point supplies an Anthropic client only when an `ANTHROPIC_API_KEY`
secret is available, and otherwise runs deterministically. The output is a drafting aid, not a
legal opinion.

This is an agent template built with the **AGENTIC STAR** development platform and the
**AgentCore Framework**. It is intended to be taken as a starting point: fork it, adapt it to
your own data and policies, and run it inside your own AGENTIC STAR deployment.

## Requirements

**This template does not run standalone.** It requires:

| Requirement | Notes |
|---|---|
| **AGENTIC STAR platform** | The agent connects to the platform at start-up. Without it, start-up fails immediately (see *Behaviour without the platform* below). Deployment guides and API documentation: [AGENTIC STAR Developers](https://developers.fd.agenticstar.tm.softbank.jp/) |
| **AgentCore Framework** (`agenticstar-agentcore`) | Installed from PyPI as a dependency. |
| Python | 3.11 or later |

```bash
pip install -e .
```

### Behaviour without the platform

The framework is designed to run **only** on AGENTIC STAR. There is no fallback or degraded
mode. If the platform is unreachable or the SDK version does not match, the agent raises
`PlatformRequired` during graph compile / start-up preflight rather than starting in a partially
working state. This is intentional — a half-running agent is worse than one that refuses to start.

## Quick Start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m pytest tests/ -v
```

Tests run without a platform connection. Running the agent itself does not.

## Project Structure

```
src/          agent implementation (nodes, services, schemas)
tests/        unit, integration and boundary tests
config/       agent configuration
docs/         design and test specification
```

See `docs/02_design.md` for the design and `docs/03_test_spec.md` for the test specification.

## Customising

1. Adjust `config/` for your own environment and policies.
2. Replace the knowledge sources and sample data with your own.
3. Review the node implementations under `src/nodes/` for domain-specific logic.
4. Re-run the test suite.

## License

MIT — see [LICENSE](LICENSE).

## Status of this repository

This template is published **as is**, by its individual author, under the MIT license. It carries
**no warranty and no support commitment**, and no organisation stands behind its behaviour or
fitness for any purpose. Issues and pull requests may or may not receive a response; that is at
the sole discretion of the repository owner.
