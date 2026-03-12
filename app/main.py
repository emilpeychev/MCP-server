import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request

from . import llm, mcp_server, prompts, retrieval
from .models import (
    AnalyzeLogRequest,
    ArgoCDInspectRequest,
    AskRepoRequest,
    AskRequest,
    ContextRequest,
    GatewayInspectRequest,
    RenderHelmRequest,
    ReviewYamlRequest,
    SearchRepoRequest,
)
from .tools.argocd_analysis import inspect_argocd_applications
from .tools.gateway_inspection import inspect_gateway_routes
from .tools.helm_render import render_helm
from .tools.log_analysis import analyze_log
from .tools.repo_search import search_repo
from .tools.yaml_review import review_yaml

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _normalize_text(value: str) -> str:
    return value.strip()


def _validate_question(question: str) -> str:
    normalized_question = _normalize_text(question)
    if not normalized_question:
        raise HTTPException(status_code=400, detail="Missing question.")
    return normalized_question


def _validate_context(content: str) -> str:
    normalized_content = _normalize_text(content)
    if not normalized_content:
        raise HTTPException(status_code=400, detail="Missing context.")
    if len(normalized_content) > llm.get_settings().max_context:
        raise HTTPException(status_code=413, detail="Context too large.")
    return normalized_content


def invoke_context_question(question: str, context: str) -> str:
    return llm.invoke_with_context(question=question, context=context, system_prompt=prompts.INFRA_ASSISTANT_PROMPT)


def invoke_question(question: str) -> str:
    return llm.invoke_question(question)


def invoke_repo_question(question: str, limit: int = 5) -> dict:
    repo_result = search_repo(question, limit=limit)
    context = prompts.build_repo_context(repo_result)
    answer = llm.invoke_with_context(question=question, context=context, system_prompt=prompts.INFRA_ASSISTANT_PROMPT)
    return {
        "response": answer,
        "sources": repo_result["files"],
        "matches": repo_result["data"].get("matches", []),
    }


@asynccontextmanager
async def lifespan(_: FastAPI):
    retrieval.index_repo()
    llm.warmup()
    yield


app = FastAPI(title="Local Infra Assistant", lifespan=lifespan)


@app.get("/healthz")
def health():
    stats = retrieval.get_index_stats()
    return {
        "status": "ok",
        "repo_path": stats["repo_path"],
        "indexed_files": stats["indexed_files"],
        "chunks": stats["chunks"],
    }


@app.get("/models")
def models():
    try:
        return llm.list_models()
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/ask")
def ask(req: AskRequest):
    question = _validate_question(req.question)
    logger.info("Question received: chars=%s", len(question))
    try:
        return {"response": invoke_question(question)}
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Ollama request failed.") from exc


@app.post("/fullcontext")
def ask_full_context(req: ContextRequest):
    question = _validate_question(req.question)
    context = _validate_context(req.content)
    logger.info("Context question received: question_chars=%s context_chars=%s", len(question), len(context))
    try:
        return {"response": invoke_context_question(question, context)}
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Ollama request failed.") from exc


@app.post("/search-repo")
def search_repo_endpoint(req: SearchRepoRequest):
    query = _validate_question(req.query)
    return search_repo(query, limit=req.limit)


@app.post("/review-yaml")
def review_yaml_endpoint(req: ReviewYamlRequest):
    yaml_content = _validate_context(req.yaml_content)
    return review_yaml(yaml_content)


@app.post("/analyze-log")
def analyze_log_endpoint(req: AnalyzeLogRequest):
    log_text = _validate_context(req.log_text)
    return analyze_log(log_text)


@app.post("/render-helm")
def render_helm_endpoint(req: RenderHelmRequest):
    chart_path = _validate_question(req.chart_path)
    return render_helm(chart_path=chart_path, values_file=req.values_file)


@app.post("/inspect-argocd")
def inspect_argocd_endpoint(req: ArgoCDInspectRequest):
    return inspect_argocd_applications(app_name=req.app_name)


@app.post("/inspect-gateway")
def inspect_gateway_endpoint(req: GatewayInspectRequest):
    return inspect_gateway_routes(hostname=req.hostname)


@app.post("/ask-repo")
def ask_repo_endpoint(req: AskRepoRequest):
    question = _validate_question(req.question)
    try:
        return invoke_repo_question(question, limit=req.limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Repo-aware reasoning failed.") from exc


@app.post("/mcp")
async def mcp_endpoint(request: Request):
    payload = await request.json()
    return mcp_server.handle_request(payload)
