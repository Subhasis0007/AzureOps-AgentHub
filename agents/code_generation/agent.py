from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol

from jinja2 import Environment, StrictUndefined
from pydantic import BaseModel, ConfigDict

from agents.code_generation.tools.devops_rest import AzureDevOpsPullRequestAdapter
from agents.code_generation.tools.git_operations import RepoContextReader
from core.state.schema import ACRGEState, MessageTrace, PullRequestSpec, RiskLevel
from core.utils.ids import pr_branch_name
from core.utils.json_schemas import validate_payload


class StructuredLLM(Protocol):
    def complete_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        output_schema: dict[str, Any],
        model: str,
    ) -> dict[str, Any]:
        ...


class CodeGenerationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    incident_id: str
    service_name: str
    environment: str
    diagnostic_summary: str
    log_summary: str
    repository: str
    candidate_files: list[str]


class CodeGenerationAgent:
    """
    Generates PR-ready, structured remediation proposals only.

    No git commands or remote writes are executed by this agent.
    """

    def __init__(
        self,
        llm_client: StructuredLLM | None = None,
        *,
        repo_root: Path | None = None,
        pr_adapter: AzureDevOpsPullRequestAdapter | None = None,
    ) -> None:
        self._llm = llm_client
        self._repo_root = repo_root or Path.cwd()
        self._reader = RepoContextReader(self._repo_root)
        self._pr_adapter = pr_adapter or AzureDevOpsPullRequestAdapter()

    def run(self, state: ACRGEState) -> ACRGEState:
        diagnostic_summary = state.diagnostic_report.summary if state.diagnostic_report else ""
        candidate_files = self._reader.list_candidate_files(limit=25)

        agent_input = CodeGenerationInput(
            incident_id=state.incident.incident_id,
            service_name=state.incident.service_name,
            environment=state.incident.environment,
            diagnostic_summary=diagnostic_summary,
            log_summary=state.log_summary,
            repository="acrge-lite",
            candidate_files=candidate_files,
        )

        pr_spec = self._build_pr_spec(agent_input)
        payload_preview = self._pr_adapter.build_pr_payload(
            title=pr_spec.title,
            description=pr_spec.body,
            source_branch=pr_spec.source_branch,
            target_branch=pr_spec.target_branch,
        )

        return state.update_from_node(
            {
                "pr_spec": pr_spec,
                "messages": [
                    *state.messages,
                    MessageTrace(
                        role="assistant",
                        content=(
                            f"Generated PR-ready remediation spec for {pr_spec.source_branch} -> "
                            f"{pr_spec.target_branch}."
                        ),
                        metadata={
                            "agent": "code_generation",
                            "pr_payload_preview": payload_preview.model_dump(mode="json"),
                        },
                    ),
                ],
                "reasoning_trace": [
                    *state.reasoning_trace,
                    f"code_generation.pr_spec_created risk={pr_spec.risk_level}",
                ],
            }
        )

    def _build_pr_spec(self, agent_input: CodeGenerationInput) -> PullRequestSpec:
        if self._llm is None:
            payload = {
                "incident_id": agent_input.incident_id,
                "repository": agent_input.repository,
                "source_branch": pr_branch_name(agent_input.incident_id),
                "target_branch": "main",
                "title": f"Fix incident {agent_input.incident_id}: targeted config remediation",
                "body": (
                    "## Summary\n"
                    "Apply minimal, targeted configuration remediation inferred from diagnostics.\n\n"
                    "## Why\n"
                    "Reduce pipeline/config drift causing recurring failures.\n\n"
                    "## Validation\n"
                    "- Re-run failing pipeline stage\n"
                    "- Verify no regression in dependent services\n"
                ),
                "diff_patch": (
                    "diff --git a/pipelines/ci.yml b/pipelines/ci.yml\n"
                    "--- a/pipelines/ci.yml\n"
                    "+++ b/pipelines/ci.yml\n"
                    "@@ -1,3 +1,5 @@\n"
                    "+# TODO: apply validated variable fallback for failed stage\n"
                ),
                "files_changed": ["pipelines/ci.yml"],
                "rollback_notes": "Revert this PR to restore previous pipeline behavior.",
                "risk_level": "medium",
            }
        else:
            context_files = []
            for rel in agent_input.candidate_files[:5]:
                excerpt = self._reader.read_file_excerpt(rel)
                if excerpt:
                    context_files.append({"path": rel, "excerpt": excerpt})

            payload = self._llm.complete_json(
                system_prompt=self._render_system_prompt(),
                user_prompt=json.dumps(
                    {
                        "input": agent_input.model_dump(mode="json"),
                        "context_files": context_files,
                    },
                    ensure_ascii=True,
                ),
                output_schema={"$ref": "pull_request_spec"},
                model="gpt-4o",
            )

        validate_payload("pull_request_spec", payload)
        if payload.get("risk_level") not in {"low", "medium", "high", "critical"}:
            payload["risk_level"] = RiskLevel.MEDIUM.value
        return PullRequestSpec.model_validate(payload)

    def _render_system_prompt(self) -> str:
        template_path = Path(__file__).parent / "prompts" / "code_generation_system.j2"
        template = Environment(undefined=StrictUndefined, autoescape=False).from_string(
            template_path.read_text(encoding="utf-8")
        )
        return template.render()
