import logging
import os
from dataclasses import dataclass

import requests
from langchain_ollama import OllamaLLM

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OllamaSettings:
    base_url: str
    model: str
    timeout: float
    max_context: int
    temperature: float
    num_predict: int
    repeat_penalty: float


def get_settings() -> OllamaSettings:
    return OllamaSettings(
        base_url=os.getenv("OLLAMA_BASE_URL", "http://ollama:11434"),
        model=os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b"),
        timeout=float(os.getenv("OLLAMA_TIMEOUT", "120")),
        max_context=int(os.getenv("MAX_CONTEXT", "15000")),
        temperature=float(os.getenv("OLLAMA_TEMPERATURE", "0.1")),
        num_predict=int(os.getenv("OLLAMA_NUM_PREDICT", "1024")),
        repeat_penalty=float(os.getenv("OLLAMA_REPEAT_PENALTY", "1.1")),
    )


def _get_client() -> OllamaLLM:
    settings = get_settings()
    return OllamaLLM(
        model=settings.model,
        base_url=settings.base_url,
        timeout=settings.timeout,
        temperature=settings.temperature,
        num_predict=settings.num_predict,
        repeat_penalty=settings.repeat_penalty,
    )


def warmup() -> None:
    settings = get_settings()
    try:
        logger.info("Warming up Ollama model '%s'", settings.model)
        _get_client().invoke("hello")
    except Exception as exc:
        logger.warning("Ollama warmup skipped: %s", exc)


def invoke_question(question: str) -> str:
    return _get_client().invoke(question)


def invoke_with_context(question: str, context: str, system_prompt: str) -> str:
    settings = get_settings()
    # Truncate context to stay within budget (rough 4 chars/token estimate)
    max_ctx_chars = settings.max_context
    if len(context) > max_ctx_chars:
        context = context[:max_ctx_chars] + "\n... [context truncated]"
    prompt = f"{system_prompt}\n\nContext:\n{context}\n\nQuestion:\n{question}"
    return _get_client().invoke(prompt)


def list_models() -> dict:
    settings = get_settings()
    try:
        response = requests.get(f"{settings.base_url}/api/tags", timeout=10)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError("Unable to fetch Ollama models.") from exc
    return response.json()