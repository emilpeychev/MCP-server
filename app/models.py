from typing import Any

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(..., description="Prompt to send directly to the model.")


class ContextRequest(BaseModel):
    question: str = Field(..., description="Question to answer using the supplied context.")
    content: str = Field(..., description="Context used to answer the question.")


class SearchRepoRequest(BaseModel):
    query: str = Field(..., description="Repo-aware search query.")
    limit: int = Field(default=5, ge=1, le=20, description="Maximum number of matches.")


class ReadFileSliceRequest(BaseModel):
    path: str = Field(..., description="Relative file path inside the indexed repository.")
    start_line: int = Field(default=1, ge=1, description="First line to read (1-based).")
    end_line: int | None = Field(default=None, description="Last line to read (inclusive).")
    max_chars: int = Field(default=2500, ge=100, le=50000, description="Hard character limit.")


class FindRelatedFilesRequest(BaseModel):
    path: str = Field(..., description="Anchor file path.")
    max_results: int = Field(default=5, ge=1, le=20, description="Maximum related files to return.")


class FindK8sObjectsRequest(BaseModel):
    kind: str | None = Field(default=None, description="Kubernetes kind filter (e.g. HTTPRoute, Service).")
    name: str | None = Field(default=None, description="Substring match on object name.")
    namespace: str | None = Field(default=None, description="Exact namespace filter.")
    max_results: int = Field(default=10, ge=1, le=50, description="Maximum objects to return.")


class SummarizeFilesRequest(BaseModel):
    paths: list[str] = Field(..., description="Relative file paths to summarize.")
    max_chars_per_file: int = Field(default=1500, ge=100, le=50000, description="Maximum preview chars per file.")
    total_budget: int = Field(default=8000, ge=500, le=200000, description="Total character budget across all files.")


class ReviewYamlRequest(BaseModel):
    yaml_content: str = Field(..., description="One or more Kubernetes YAML documents.")


class CompressLogsRequest(BaseModel):
    log_text: str = Field(..., description="Raw Kubernetes, Tekton, or ArgoCD logs.")
    max_chars: int = Field(default=3000, ge=100, le=50000, description="Maximum excerpt characters.")


class AnalyzeLogRequest(BaseModel):
    log_text: str = Field(..., description="Raw Kubernetes, Tekton, or ArgoCD logs.")


class RenderHelmRequest(BaseModel):
    chart_path: str = Field(..., description="Path to the Helm chart.")
    values_file: str | None = Field(default=None, description="Optional values file.")
    summary_only: bool = Field(default=True, description="Return object summary instead of full output.")
    max_chars: int = Field(default=4000, ge=100, le=100000, description="Hard character limit on output.")


class ArgoCDInspectRequest(BaseModel):
    app_name: str | None = Field(default=None, description="Optional ArgoCD Application name filter.")


class GatewayInspectRequest(BaseModel):
    hostname: str | None = Field(default=None, description="Optional hostname filter for Gateway API resources.")


class CopilotBriefRequest(BaseModel):
    question: str = Field(..., description="The original infrastructure question.")
    findings: list[str] | None = Field(default=None, description="Key findings from summarization tools.")
    affected_files: list[str] | None = Field(default=None, description="Relevant file paths.")
    likely_cause: str | None = Field(default=None, description="Probable root cause.")
    verbosity: str = Field(default="compact", description="Output verbosity: compact, normal, or detailed.")
    detected_pattern: str | None = Field(default=None, description="Problem pattern from classifier.")
    confidence: float | None = Field(default=None, description="Classifier confidence (0.0-1.0).")
    relevant_resources: list[str] | None = Field(default=None, description="K8s resources involved.")
    checks_performed: list[str] | None = Field(default=None, description="Checks already performed.")
    missing_evidence: list[str] | None = Field(default=None, description="Evidence not yet gathered.")
    recommended_next_step: str | None = Field(default=None, description="Next recommended action.")
    ask_copilot: str | None = Field(default=None, description="Specific question for Copilot.")
    past_causes: list[str] | None = Field(default=None, description="Root causes from past similar issues.")


class ClassifyProblemRequest(BaseModel):
    text: str = Field(..., description="Question, error message, or log snippet to classify.")
    top_n: int = Field(default=3, ge=1, le=10, description="Maximum pattern matches to return.")


class GetPlaybookRequest(BaseModel):
    pattern: str = Field(..., description="Problem pattern name (e.g. crashloop_backoff).")


class RecordIssueRequest(BaseModel):
    pattern: str = Field(..., description="Problem pattern name.")
    resource: str = Field(default="", description="Primary resource involved.")
    root_cause: str = Field(default="", description="Identified root cause.")
    findings: list[str] = Field(default_factory=list, description="Key findings.")
    tools_used: list[str] = Field(default_factory=list, description="Tools called during diagnosis.")
    tool_order: list[str] = Field(default_factory=list, description="Order of tool calls.")
    resolved: bool = Field(default=False, description="Whether the issue was resolved.")


class QueryHistoryRequest(BaseModel):
    pattern: str = Field(..., description="Problem pattern to look up history for.")


class AskRepoRequest(BaseModel):
    question: str = Field(..., description="Infrastructure question to answer from repo context.")
    limit: int = Field(default=5, ge=1, le=20, description="Maximum number of retrieved matches.")


class ToolResponse(BaseModel):
    result: str
    files: list[str] = Field(default_factory=list)
    data: dict[str, Any] = Field(default_factory=dict)
