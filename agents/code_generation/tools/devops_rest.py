from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PullRequestDraftPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=8)
    description: str = Field(min_length=20)
    source_ref_name: str = Field(min_length=5)
    target_ref_name: str = Field(min_length=1)


class AzureDevOpsPullRequestAdapter:
    """
    Adapter for Azure DevOps PR interactions.

    This phase only builds draft payloads; no remote execution is performed.
    """

    def build_pr_payload(
        self,
        *,
        title: str,
        description: str,
        source_branch: str,
        target_branch: str,
    ) -> PullRequestDraftPayload:
        return PullRequestDraftPayload(
            title=title,
            description=description,
            source_ref_name=f"refs/heads/{source_branch}",
            target_ref_name=f"refs/heads/{target_branch}",
        )
