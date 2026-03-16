from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Callable, TypeVar

logger = logging.getLogger(__name__)

_DEFAULT_SERVER_NAME = "local-infra-assistant"
_DEFAULT_MCP_JSON_PATH = "/workspace/.vscode/mcp.json"

_cache_mtime_ns: int | None = None
_cache_path: str | None = None
_cache_overrides: dict[str, str] = {}

T = TypeVar("T")


def _load_vscode_env_overrides() -> dict[str, str]:
    global _cache_mtime_ns, _cache_path, _cache_overrides

    config_path = os.getenv("VSCODE_MCP_JSON_PATH", _DEFAULT_MCP_JSON_PATH).strip()
    if not config_path:
        return {}

    path = Path(config_path)
    if not path.exists():
        return {}

    try:
        mtime_ns = path.stat().st_mtime_ns
    except OSError:
        return {}

    if _cache_path == config_path and _cache_mtime_ns == mtime_ns:
        return _cache_overrides

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Unable to parse VS Code MCP JSON '%s': %s", config_path, exc)
        return {}

    server_name = os.getenv("VSCODE_MCP_SERVER_NAME", _DEFAULT_SERVER_NAME)
    server_cfg = data.get("servers", {}).get(server_name, {})
    env_cfg = server_cfg.get("env", {})

    if not isinstance(env_cfg, dict):
        logger.warning("Invalid 'env' section in '%s' for server '%s'", config_path, server_name)
        return {}

    normalized: dict[str, str] = {}
    for key, value in env_cfg.items():
        if not isinstance(key, str):
            continue
        if value is None:
            continue
        normalized[key] = str(value)

    _cache_path = config_path
    _cache_mtime_ns = mtime_ns
    _cache_overrides = normalized
    return _cache_overrides


def get_config_value(key: str, default: T, caster: Callable[[str], T] | None = None) -> T:
    overrides = _load_vscode_env_overrides()
    raw_value = overrides.get(key, os.getenv(key, str(default)))

    if caster is None:
        return raw_value  # type: ignore[return-value]

    try:
        return caster(raw_value)
    except (TypeError, ValueError):
        logger.warning("Invalid value for '%s': %s. Falling back to default.", key, raw_value)
        return default
