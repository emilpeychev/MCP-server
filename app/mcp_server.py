from __future__ import annotations

from fastapi.responses import JSONResponse

from .classifier import classify_to_dict
from .issue_memory import query_history_dict, record_issue_dict
from .playbooks import playbook_to_dict
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
            "key findings, affected files, detected pattern, and likely cause into one compact payload. "
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
                "detected_pattern": {
                    "type": ["string", "null"],
                    "description": "Problem pattern from classify_problem (e.g. crashloop_backoff).",
                },
                "confidence": {
                    "type": ["number", "null"],
                    "description": "Classifier confidence (0.0-1.0).",
                },
                "relevant_resources": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "K8s resources involved (e.g. Deployment/my-app).",
                },
                "checks_performed": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of checks already performed.",
                },
                "missing_evidence": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Evidence that could not be gathered (e.g. cluster access needed).",
                },
                "recommended_next_step": {
                    "type": ["string", "null"],
                    "description": "What to do next if the issue is not yet resolved.",
                },
                "ask_copilot": {
                    "type": ["string", "null"],
                    "description": "Specific question for Copilot to answer.",
                },
                "past_causes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Root causes from past similar issues (from issue history).",
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
            detected_pattern=args.get("detected_pattern"),
            confidence=args.get("confidence"),
            relevant_resources=args.get("relevant_resources"),
            checks_performed=args.get("checks_performed"),
            missing_evidence=args.get("missing_evidence"),
            recommended_next_step=args.get("recommended_next_step"),
            ask_copilot=args.get("ask_copilot"),
            past_causes=args.get("past_causes"),
        ),
    },
}

# Combined registry — used by the MCP handler.

# ---------------------------------------------------------------------------
# Layer 3 — Diagnostic tools
# These tools CLASSIFY problems, look up PLAYBOOKS, and manage ISSUE HISTORY.
# They tie the retrieval + summarization layers into guided troubleshooting.
# ---------------------------------------------------------------------------
DIAGNOSTIC_TOOLS = {
    "classify_problem": {
        "description": (
            "Classify a question or log snippet into a known problem pattern (e.g. crashloop_backoff, argocd_out_of_sync). "
            "Returns ranked patterns with confidence and matching signals. "
            "Call this FIRST to guide which playbook and tools to use."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Question, error message, or log snippet to classify.",
                },
                "top_n": {
                    "type": "integer",
                    "default": 3,
                    "description": "Maximum number of pattern matches to return.",
                },
            },
            "required": ["text"],
        },
        "handler": lambda args: classify_to_dict(args["text"], top_n=args.get("top_n", 3)),
    },
    "get_playbook": {
        "description": (
            "Get the troubleshooting playbook for a detected problem pattern. "
            "Returns ordered steps, common root causes, stop conditions, and key resources. "
            "Use this after classify_problem to know what to check and in what order."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Problem pattern name (e.g. 'crashloop_backoff', 'argocd_out_of_sync').",
                },
            },
            "required": ["pattern"],
        },
        "handler": lambda args: playbook_to_dict(args["pattern"]),
    },
    "record_issue": {
        "description": (
            "Record a troubleshooting issue to the persistent issue memory. "
            "Store the pattern, resource, root cause, findings, and tools used. "
            "Call this after resolving or after a diagnostic session to build history."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Problem pattern name.",
                },
                "resource": {
                    "type": "string",
                    "description": "Primary resource involved (e.g. 'Deployment/my-app').",
                    "default": "",
                },
                "root_cause": {
                    "type": "string",
                    "description": "Identified root cause.",
                    "default": "",
                },
                "findings": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Key findings from the diagnostic session.",
                },
                "tools_used": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Tools that were called during diagnosis.",
                },
                "tool_order": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Order in which tools were called.",
                },
                "resolved": {
                    "type": "boolean",
                    "default": False,
                    "description": "Whether the issue was resolved.",
                },
            },
            "required": ["pattern"],
        },
        "handler": lambda args: record_issue_dict(args),
    },
    "query_history": {
        "description": (
            "Query the issue memory for past issues matching a problem pattern. "
            "Returns past issues, common root causes, and the best tool order from resolved issues. "
            "Use this to prioritize what to check based on what worked before."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Problem pattern to look up history for.",
                },
            },
            "required": ["pattern"],
        },
        "handler": lambda args: query_history_dict(args["pattern"]),
    },
}

TOOLS = {**RETRIEVAL_TOOLS, **SUMMARIZATION_TOOLS, **DIAGNOSTIC_TOOLS}


def handle_request(payload: dict) -> JSONResponse:
    method = payload.get("method")
    request_id = payload.get("id")

    try:
        if method == "initialize":
            return _response(
                request_id,
                {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {"name": "local-infra-assistant", "version": "0.3.0"},
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