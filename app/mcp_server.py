from __future__ import annotations

from fastapi.responses import JSONResponse

from .tools.argocd_analysis import inspect_argocd_applications
from .tools.gateway_inspection import inspect_gateway_routes
from .tools.helm_render import render_helm
from .tools.log_analysis import analyze_log
from .tools.repo_search import search_repo
from .tools.yaml_review import review_yaml

TOOLS = {
    "search_repo": {
        "description": "Search the locally indexed repository for infrastructure-related definitions and snippets. Use the query argument with a search string such as 'HTTPRoute' or 'Gateway API'. Do not pass repository URLs.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search string to run against the locally indexed repository.",
                },
                "limit": {
                    "type": "integer",
                    "default": 5,
                    "description": "Maximum number of matches to return.",
                },
            },
            "required": ["query"],
            "examples": [
                {"query": "HTTPRoute"},
                {"query": "Gateway API", "limit": 5},
            ],
        },
        "handler": lambda arguments: search_repo(arguments["query"], limit=arguments.get("limit", 5)),
    },
    "review_yaml": {
        "description": "Review Kubernetes YAML for hostname, LoadBalancer, and Gateway API issues.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "yaml_content": {"type": "string"},
            },
            "required": ["yaml_content"],
        },
        "handler": lambda arguments: review_yaml(arguments["yaml_content"]),
    },
    "render_helm": {
        "description": "Render a Helm chart with helm template.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "chart_path": {"type": "string"},
                "values_file": {"type": ["string", "null"]},
            },
            "required": ["chart_path"],
        },
        "handler": lambda arguments: render_helm(arguments["chart_path"], values_file=arguments.get("values_file")),
    },
    "analyze_log": {
        "description": "Analyze Kubernetes, Tekton, or ArgoCD logs for likely failure modes.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "log_text": {"type": "string"},
            },
            "required": ["log_text"],
        },
        "handler": lambda arguments: analyze_log(arguments["log_text"]),
    },
    "inspect_argocd": {
        "description": "Inspect ArgoCD Application manifests in the indexed repo and report drift or config risks.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "app_name": {"type": ["string", "null"]},
            },
        },
        "handler": lambda arguments: inspect_argocd_applications(app_name=arguments.get("app_name")),
    },
    "inspect_gateway": {
        "description": "Inspect Gateway and HTTPRoute resources in the indexed repo and surface routing risks.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "hostname": {"type": ["string", "null"]},
            },
        },
        "handler": lambda arguments: inspect_gateway_routes(hostname=arguments.get("hostname")),
    },
}


def handle_request(payload: dict) -> JSONResponse:
    method = payload.get("method")
    request_id = payload.get("id")

    try:
        if method == "initialize":
            return _response(
                request_id,
                {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {"name": "local-infra-assistant", "version": "0.1.0"},
                    "capabilities": {"tools": {}},
                },
            )
        if method == "ping":
            return _response(request_id, {"pong": True})
        if method == "tools/list":
            tools = []
            for name, definition in TOOLS.items():
                tools.append(
                    {
                        "name": name,
                        "description": definition["description"],
                        "inputSchema": definition["inputSchema"],
                    }
                )
            return _response(request_id, {"tools": tools})
        if method == "tools/call":
            params = payload.get("params", {})
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            if tool_name not in TOOLS:
                return _error(request_id, -32601, f"Unknown tool: {tool_name}")
            result = TOOLS[tool_name]["handler"](arguments)
            return _response(
                request_id,
                {
                    "content": [{"type": "text", "text": result["result"]}],
                    "structuredContent": result,
                    "isError": False,
                },
            )
        if method == "notifications/initialized":
            return JSONResponse(status_code=202, content={})
        return _error(request_id, -32601, f"Unsupported method: {method}")
    except Exception as exc:
        return _error(request_id, -32000, str(exc))


def _response(request_id: int | str | None, result: dict) -> JSONResponse:
    return JSONResponse({"jsonrpc": "2.0", "id": request_id, "result": result})


def _error(request_id: int | str | None, code: int, message: str) -> JSONResponse:
    return JSONResponse({"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}, status_code=400)