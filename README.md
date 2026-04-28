# ACRGE Lite

Autonomous Cloud Reliability and Governance Engine (Lite) is an enterprise Azure-native multi-agent platform for incident detection, diagnosis, remediation proposal, and governed execution across DevOps, integration, and data pipelines.

## Status

Phase 1 complete:
- Base monorepo structure created
- Project metadata and dependency management established
- Environment and security scaffolding added

Next planned phase:
- Phase 2 (`core/state/schema.py`, `core/config/settings.py`, `core/utils/*`, `core/telemetry/setup.py`)

## Product Scope

ACRGE Lite ingests incident signals from:
- Azure DevOps pipeline failures
- Azure Service Bus deadletter and Logic App integration failures
- Azure Data Factory and Databricks pipeline failures

The platform routes incidents through specialized AI agents to deliver:
- Incident classification and routing
- Log and evidence analysis
- Root cause diagnostics
- Code/config remediation proposals
- PR drafting and governance decisions
- Full auditability and observability

## Target Architecture

Five-tier event-driven architecture:
1. Ingestion Layer
2. Orchestration Layer (Azure Functions + LangGraph)
3. AI and Knowledge Layer (Azure OpenAI + AI Search RAG)
4. Data and State Layer (Cosmos DB, Redis, Blob, Key Vault, App Config)
5. Action and Feedback Layer (Azure DevOps, Teams, Monitor, App Insights)

## Repository Layout

```text
acrge-lite/
  .github/workflows/
  agents/
    supervisor/
    diagnostic/
    log_analysis/
    code_generation/
    governance/
    cost_optimization/
  core/
    state/
    graph/
    memory/
    optimization/
    telemetry/
    config/
    utils/
  services/
    ingest/
    executor/
    notifier/
  infra/
    bicep/
    terraform/
  pipelines/
  rag/
    indexer/
    schemas/
  tests/
    unit/
    integration/
    e2e/
  docs/
    runbooks/
  pyproject.toml
  .env.example
  .gitignore
  README.md
```

## Local Setup

Prerequisites:
- Python 3.11
- Recommended: virtual environment (`.venv`)

Commands:

```bash
python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
pip install -e .[dev]
```

## Engineering Standards

- Typed Python 3.11 code with strict validation (Pydantic v2)
- Structured logging and telemetry-first design
- Secure defaults with managed identity-first integrations
- No hardcoded secrets; local dev through `.env` only
- Testability via unit, integration, and e2e test layers

## Security Notes

- Keep `.env` local; never commit secret values.
- Production auth should use managed identities and Key Vault.
- Auto-remediation remains disabled by default unless policy allows.

## Planned Phases

1. Foundation files and skeleton layout (this phase)
2. Core state/config/utilities/telemetry
3. LangGraph orchestration core
4. Agent modules and prompts
5. Azure Function applications and normalizers
6. RAG indexers and adapter tools
7. Infra modules and pipeline YAML
8. Test suites
9. Docker and final documentation hardening
