from __future__ import annotations

from fastapi.responses import JSONResponse

from .tools.argocd_analysis import inspect_argocd_applications
from .tools.copilot_brief import prepare_copilot_brief
from .tools.file_finder import find_related_files
from .tools.file_reader import read_file_slice
from .tools.file_summarizer import summarize_files
from .tools.gateway_inspection import inspect_gateway_routes
from .tools.helm_render import render_helm
from .tools.k8s_finder import find_k8s_objects
from .tools.log_analysis import compress_logs
from .tools.repo_search import search_repo
from .tools.yaml_review import review_yaml

# ---------------------------------------------------------------------------
# Layer 1 — Retrieval tools
# These tools FIND and FETCH only what is needed.
# They return: file paths, line ranges, object names, short excerpts.
# They do NOT summarize, reason, or produce recommendations.
# ---------------------------------------------------------------------------
RETRIEVAL_TOOLS = {
    "search_repo": {
        "description": (
            "Search the locally indexed repository for infrastructure-related files and snippets. "
            "Returns ranked file paths and short excerpts — not full file content. "
            "Use this first when investigating a problem. "
            "Does NOT summarize or explain; use a summarization tool after."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search string (e.g. 'HTTPRoute', 'Harbor hostname').",
                },
                "max_results": {
                    "type": "integer",
                    "default": 3,
                    "description": "Maximum number of matches to return (default: 3).",
                },
            },
            "required": ["query"],
        },
        "handler": lambda args: search_repo(args["query"], limit=args.get("max_results", 3)),
    },
    "read_file_slice": {
        "description": (
            "Read a small slice of a repository file by line range. "
            "Returns the requested lines and total line count. "
            "Use this after search_repo to fetch specific sections. "
            "Does NOT return full files by default — specify start_line/end_line."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative file path inside the indexed repository.",
                },
                "start_line": {
                    "type": "integer",
                    "default": 1,
                    "description": "First line to read (1-based).",
                },
                "end_line": {
                    "type": ["integer", "null"],
                    "default": None,
                    "description": "Last line to read (inclusive). Defaults to start_line + 50.",
                },
                "max_chars": {
                    "type": "integer",
                    "default": 3000,
                    "description": "Hard character limit on the returned content.",
                },
            },
            "required": ["path"],
        },
        "handler": lambda args: read_file_slice(
            args["path"],
            start_line=args.get("start_line", 1),
            end_line=args.get("end_line"),
            max_chars=args.get("max_chars", 3000),
        ),
    },
    "find_related_files": {
        "description": (
            "Given a file path, find related files by directory proximity and name similarity. "
            "Returns a short list of file paths only — no content. "
            "Use this to discover sibling manifests, values files, or supporting configs."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative file path to use as the anchor.",
                },
                "max_results": {
                    "type": "integer",
                    "default": 5,
                    "description": "Maximum number of related files to return.",
                },
            },
            "required": ["path"],
        },
        "handler": lambda args: find_related_files(args["path"], max_results=args.get("max_results", 5)),
    },
    "find_k8s_objects": {
        "description": (
            "Find Kubernetes objects in the repo by kind, name, or namespace. "
            "Returns a list of object metadata (kind, name, namespace, file) — not full YAML. "
            "Use this to locate specific resources before reading or summarizing them."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "kind": {
                    "type": ["string", "null"],
                    "description": "Kubernetes kind filter (e.g. 'HTTPRoute', 'Service').",
                },
                "name": {
                    "type": ["string", "null"],
                    "description": "Substring match on object name.",
                },
                "namespace": {
                    "type": ["string", "null"],
                    "description": "Exact namespace filter.",
                },
                "max_results": {
                    "type": "integer",
                    "default": 10,
                    "description": "Maximum number of objects to return.",
                },
            },
        },
        "handler": lambda args: find_k8s_objects(
            kind=args.get("kind"),
            name=args.get("name"),
            namespace=args.get("namespace"),
            max_results=args.get("max_results", 10),
        ),
    },
}

# ---------------------------------------------------------------------------
# Layer 2 — Summarization tools
# These tools COMPRESS and PREPARE context for Copilot.
# They return: findings, warnings, likely cause, affected files, short briefs.
# They should receive pre-fetched content from retrieval tools.
# ---------------------------------------------------------------------------
SUMMARIZATION_TOOLS = {
    "summarize_files": {
        "description": (
            "Summarize one or more repo files. Returns structured overview per file: "
            "line count, type, Kubernetes objects found, and a short preview. "
            "Use this after retrieving file paths with search_repo or find_k8s_objects."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of relative file paths to summarize.",
                },
                "max_chars_per_file": {
                    "type": "integer",
                    "default": 1500,
                    "description": "Maximum preview characters per file.",
                },
                "total_budget": {
                    "type": "integer",
                    "default": 8000,
                    "description": "Total character budget across all files. Per-file limit is auto-reduced to fit.",
                },
            },
            "required": ["paths"],
        },
        "handler": lambda args: summarize_files(
            args["paths"],
            max_chars_per_file=args.get("max_chars_per_file", 1500),
            total_budget=args.get("total_budget", 8000),
        ),
    },
    "review_yaml": {
        "description": (
            "Review Kubernetes YAML for hostname conflicts, LoadBalancer issues, and Gateway API misconfigurations. "
            "Returns structured findings with severity. "
            "Does NOT fetch files — pass the YAML content directly."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "yaml_content": {
                    "type": "string",
                    "description": "Raw YAML content to review.",
                },
            },
            "required": ["yaml_content"],
        },
        "handler": lambda args: review_yaml(args["yaml_content"]),
    },
    "compress_logs": {
        "description": (
            "Compress raw Kubernetes, Tekton, or ArgoCD logs into structured signals and suggestions. "
            "Returns: log type, failure signals, actionable suggestions, and a short excerpt of key error lines. "
            "Does NOT return the full log — only the distilled summary."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "log_text": {
                    "type": "string",
                    "description": "Raw log text to compress.",
                },
                "max_chars": {
                    "type": "integer",
                    "default": 2500,
                    "description": "Maximum characters for the excerpt.",
                },
            },
            "required": ["log_text"],
        },
        "handler": lambda args: compress_logs(args["log_text"], max_chars=args.get("max_chars", 3000)),
    },
    "render_helm": {
        "description": (
            "Render a Helm chart and return a summary of produced objects. "
            "By default returns object list + preview only (summary_only=true). "
            "Set summary_only=false to get the full rendered output (capped at max_chars). "
            "Does NOT run helm install — read-only template rendering."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "chart_path": {
                    "type": "string",
                    "description": "Path to the Helm chart directory.",
                },
                "values_file": {
                    "type": ["string", "null"],
                    "description": "Optional values override file.",
                },
                "summary_only": {
                    "type": "boolean",
                    "default": True,
                    "description": "Return object summary instead of full rendered output.",
                },
                "max_chars": {
                    "type": "integer",
                    "default": 4000,
                    "description": "Hard character limit on output.",
                },
            },
            "required": ["chart_path"],
        },
        "handler": lambda args: render_helm(
            args["chart_path"],
            values_file=args.get("values_file"),
            summary_only=args.get("summary_only", True),
            max_chars=args.get("max_chars", 4000),
        ),
    },
    "inspect_argocd": {
        "description": (
            "Inspect ArgoCD Application manifests in the indexed repo. "
            "Returns: application metadata, sync policy, and structured findings (drift risks, missing fields). "
            "Optionally filter by app_name."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "app_name": {
                    "type": ["string", "null"],
                    "description": "Optional ArgoCD Application name filter.",
                },
            },
        },
        "handler": lambda args: inspect_argocd_applications(app_name=args.get("app_name")),
    },
    "inspect_gateway": {
        "description": (
            "Inspect Gateway and HTTPRoute resources in the indexed repo. "
            "Returns: route metadata, parent refs, and structured findings (missing refs, broad matches). "
            "Optionally filter by hostname."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "hostname": {
                    "type": ["string", "null"],
                    "description": "Optional hostname filter for Gateway API resources.",
                },
            },
        },
        "handler": lambda args: inspect_gateway_routes(hostname=args.get("hostname")),
    },
    "prepare_copilot_brief": {
        "description": (
            "Final handoff tool. Builds a structured, distilled brief for Copilot from previous tool results. "
            "Call this LAST, after retrieval and summarization, to package the question, "
            "key findings, affected files, and likely cause into one compact payload. "
            "Copilot should receive this brief and then provide the fix."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The original infrastructure question.",
                },
                "findings": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Key findings from summarization tools.",
                },
                "affected_files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Relevant file paths discovered during retrieval.",
                },
                "likely_cause": {
                    "type": ["string", "null"],
                    "description": "Short description of the probable root cause.",
                },
                "verbosity": {
                    "type": "string",
                    "enum": ["compact", "normal", "detailed"],
                    "default": "compact",
                    "description": "Output verbosity: compact (≤500 chars), normal (≤1500), detailed (≤5000).",
                },
            },
            "required": ["question"],
        },
        "handler": lambda args: prepare_copilot_brief(
            question=args["question"],
            findings=args.get("findings"),
            affected_files=args.get("affected_files"),
            likely_cause=args.get("likely_cause"),
            verbosity=args.get("verbosity", "compact"),
        ),
    },
}

# Combined registry — used by the MCP handler.
TOOLS = {**RETRIEVAL_TOOLS, **SUMMARIZATION_TOOLS}


def handle_request(payload: dict) -> JSONResponse:
    method = payload.get("method")
    request_id = payload.get("id")

    try:
        if method == "initialize":
            return _response(
                request_id,
                {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {"name": "local-infra-assistant", "version": "0.2.0"},
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