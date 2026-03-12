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


class ReviewYamlRequest(BaseModel):
    yaml_content: str = Field(..., description="One or more Kubernetes YAML documents.")


class AnalyzeLogRequest(BaseModel):
    log_text: str = Field(..., description="Raw Kubernetes, Tekton, or ArgoCD logs.")


class RenderHelmRequest(BaseModel):
    chart_path: str = Field(..., description="Path to the Helm chart.")
    values_file: str | None = Field(default=None, description="Optional values file.")


class ArgoCDInspectRequest(BaseModel):
    app_name: str | None = Field(default=None, description="Optional ArgoCD Application name filter.")


class GatewayInspectRequest(BaseModel):
    hostname: str | None = Field(default=None, description="Optional hostname filter for Gateway API resources.")


class AskRepoRequest(BaseModel):
    question: str = Field(..., description="Infrastructure question to answer from repo context.")
    limit: int = Field(default=5, ge=1, le=20, description="Maximum number of retrieved matches.")


class ToolResponse(BaseModel):
    result: str
    files: list[str] = Field(default_factory=list)
    data: dict[str, Any] = Field(default_factory=dict)
