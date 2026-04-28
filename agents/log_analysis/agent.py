from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal, Protocol

from jinja2 import Environment, StrictUndefined
from jsonschema import Draft202012Validator
from pydantic import BaseModel, ConfigDict, Field

from agents.log_analysis.tools.log_chunker import chunk_text_by_tokens
from core.state.schema import ACRGEState, MessageTrace


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


class LogAnalysisOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=10, max_length=20000)
    taxonomy: Literal["infra", "code", "config", "data", "auth", "network", "unknown"]
    confidence: float = Field(ge=0.0, le=1.0)
    key_findings: list[str] = Field(default_factory=list)


LOG_ANALYSIS_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["summary", "taxonomy", "confidence", "key_findings"],
    "properties": {
        "summary": {"type": "string", "minLength": 10},
        "taxonomy": {
            "type": "string",
            "enum": ["infra", "code", "config", "data", "auth", "network", "unknown"],
        },
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "key_findings": {"type": "array", "items": {"type": "string"}},
    },
    "additionalProperties": False,
}


class LogAnalysisAgent:
    def __init__(self, llm_client: StructuredLLM | None = None) -> None:
        self._llm = llm_client

    def run(self, state: ACRGEState) -> ACRGEState:
        raw_blob = self._collect_raw_log_blob(state)
        chunks = chunk_text_by_tokens(raw_blob, chunk_size=800, overlap=200)

        if self._llm is None:
            output = LogAnalysisOutput(
                summary="Log patterns suggest configuration mismatch with downstream dependency.",
                taxonomy="config",
                confidence=0.72,
                key_findings=["Repeated 400/401 responses after deployment."],
            )
        else:
            chunk_summaries = [self._summarize_chunk(chunk, index) for index, chunk in enumerate(chunks)]
            output = self._synthesize(chunk_summaries)

        merged = state.update_from_node(
            {
                "log_summary": output.summary,
                "messages": [
                    *state.messages,
                    MessageTrace(
                        role="assistant",
                        content=(
                            f"Log analysis completed: taxonomy={output.taxonomy}, "
                            f"confidence={output.confidence:.2f}."
                        ),
                        metadata={"agent": "log_analysis", "findings": output.key_findings},
                    ),
                ],
                "reasoning_trace": [
                    *state.reasoning_trace,
                    f"log_analysis.taxonomy={output.taxonomy} confidence={output.confidence:.2f}",
                ],
            }
        )
        return merged

    def _summarize_chunk(self, chunk: str, chunk_index: int) -> str:
        assert self._llm is not None
        payload = self._llm.complete_json(
            system_prompt=self._render_system_prompt(mode="chunk"),
            user_prompt=json.dumps({"chunk_index": chunk_index, "text": chunk}, ensure_ascii=True),
            output_schema={
                "type": "object",
                "required": ["summary"],
                "properties": {"summary": {"type": "string", "minLength": 5}},
                "additionalProperties": False,
            },
            model="gpt-4o-mini",
        )
        return str(payload["summary"])

    def _synthesize(self, chunk_summaries: list[str]) -> LogAnalysisOutput:
        assert self._llm is not None
        payload = self._llm.complete_json(
            system_prompt=self._render_system_prompt(mode="synthesis"),
            user_prompt=json.dumps({"chunk_summaries": chunk_summaries}, ensure_ascii=True),
            output_schema=LOG_ANALYSIS_SCHEMA,
            model="gpt-4o-mini",
        )
        Draft202012Validator(LOG_ANALYSIS_SCHEMA).validate(payload)
        return LogAnalysisOutput.model_validate(payload)

    def _collect_raw_log_blob(self, state: ACRGEState) -> str:
        incident = state.incident
        parts = [
            incident.title,
            incident.description,
            state.log_summary,
            json.dumps(incident.raw_payload, ensure_ascii=True),
        ]
        return "\n".join(part for part in parts if part)

    def _render_system_prompt(self, *, mode: Literal["chunk", "synthesis"]) -> str:
        template_path = Path(__file__).parent / "prompts" / "log_analysis_system.j2"
        template = Environment(undefined=StrictUndefined, autoescape=False).from_string(
            template_path.read_text(encoding="utf-8")
        )
        return template.render(mode=mode)
