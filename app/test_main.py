from pathlib import Path
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app.main as main_module
import app.tools.repo_search as repo_search_tool

client = TestClient(main_module.app)


def test_healthz(monkeypatch):
    monkeypatch.setattr(main_module.retrieval, "get_index_stats", lambda: {"repo_path": "/repo", "indexed_files": 3, "chunks": 7})

    response = client.get("/healthz")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["repo_path"] == "/repo"
    assert data["indexed_files"] == 3
    assert data["chunks"] == 7
    assert "cache" in data


def test_fullcontext_success(monkeypatch):
    monkeypatch.setattr(main_module, "invoke_context_question", lambda question, context: "Mocked answer")

    payload = {
        "question": "What is Harbor?",
        "content": "Harbor is a registry used by the platform team.",
    }
    response = client.post("/fullcontext", json=payload)

    assert response.status_code == 200
    assert response.json() == {"response": "Mocked answer"}


def test_fullcontext_missing_fields():
    response = client.post("/fullcontext", json={"question": "", "content": ""})

    assert response.status_code == 400
    assert response.json()["detail"] == "Missing question."


def test_fullcontext_rejects_large_context(monkeypatch):
    monkeypatch.setattr(main_module.llm, "get_settings", lambda: type("Settings", (), {"max_context": 10})())

    response = client.post("/fullcontext", json={"question": "What failed?", "content": "x" * 11})

    assert response.status_code == 413
    assert response.json()["detail"] == "Context too large."


def test_search_repo_endpoint(monkeypatch):
    monkeypatch.setattr(main_module, "search_repo", lambda query, limit=5: {"result": "ok", "files": ["repo.yaml"], "data": {"matches": []}})

    response = client.post("/search-repo", json={"query": "Harbor hostname", "limit": 3})

    assert response.status_code == 200
    assert response.json()["files"] == ["repo.yaml"]


def test_review_yaml_endpoint(monkeypatch):
    monkeypatch.setattr(main_module, "review_yaml", lambda yaml_content: {"result": "reviewed", "files": [], "data": {"findings": []}})

    response = client.post("/review-yaml", json={"yaml_content": "kind: Service"})

    assert response.status_code == 200
    assert response.json()["result"] == "reviewed"


def test_analyze_log_endpoint(monkeypatch):
    monkeypatch.setattr(main_module, "analyze_log", lambda log_text: {"result": "argocd sync failure", "files": [], "data": {"signals": ["sync failed"]}})

    response = client.post("/analyze-log", json={"log_text": "argocd app sync failed"})

    assert response.status_code == 200
    assert response.json()["data"]["signals"] == ["sync failed"]


def test_ask_repo_endpoint(monkeypatch):
    monkeypatch.setattr(main_module, "invoke_repo_question", lambda question, limit=5: {"response": "Harbor lives in values.yaml", "sources": ["charts/harbor/values.yaml"], "matches": []})

    response = client.post("/ask-repo", json={"question": "Where is Harbor hostname defined?", "limit": 4})

    assert response.status_code == 200
    assert response.json()["response"] == "Harbor lives in values.yaml"


def test_models_success(monkeypatch):
    monkeypatch.setattr(main_module.llm, "list_models", lambda: {"models": [{"name": "qwen2.5-coder:7b"}]})

    response = client.get("/models")

    assert response.status_code == 200
    assert response.json() == {"models": [{"name": "qwen2.5-coder:7b"}]}


def test_mcp_tools_list():
    response = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})

    assert response.status_code == 200
    tools = response.json()["result"]["tools"]
    tool_names = [t["name"] for t in tools]
    # Retrieval layer
    assert "search_repo" in tool_names
    assert "read_file_slice" in tool_names
    assert "find_related_files" in tool_names
    assert "find_k8s_objects" in tool_names
    # Summarization layer
    assert "summarize_files" in tool_names
    assert "review_yaml" in tool_names
    assert "compress_logs" in tool_names
    assert "render_helm" in tool_names
    assert "inspect_argocd" in tool_names
    assert "inspect_gateway" in tool_names
    assert "prepare_copilot_brief" in tool_names


def test_inspect_argocd_endpoint(monkeypatch):
    monkeypatch.setattr(main_module, "inspect_argocd_applications", lambda app_name=None: {"result": "inspected", "files": ["argocd/app.yaml"], "data": {"applications": []}})

    response = client.post("/inspect-argocd", json={"app_name": "platform"})

    assert response.status_code == 200
    assert response.json()["files"] == ["argocd/app.yaml"]


def test_inspect_gateway_endpoint(monkeypatch):
    monkeypatch.setattr(main_module, "inspect_gateway_routes", lambda hostname=None: {"result": "gateway checked", "files": ["gateway/route.yaml"], "data": {"routes": []}})

    response = client.post("/inspect-gateway", json={"hostname": "harbor.example.com"})

    assert response.status_code == 200
    assert response.json()["result"] == "gateway checked"


def test_mcp_tool_call_search_repo(monkeypatch):
    monkeypatch.setattr(main_module.mcp_server, "search_repo", lambda query, limit=5: {"result": "Found 1 repository match.", "files": ["charts/harbor/values.yaml"], "data": {"matches": [{"path": "charts/harbor/values.yaml"}]}})
    main_module.mcp_server.TOOLS["search_repo"]["handler"] = lambda arguments: main_module.mcp_server.search_repo(arguments["query"], limit=arguments.get("max_results", 5))

    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "search_repo", "arguments": {"query": "Harbor hostname", "max_results": 1}},
        },
    )

    assert response.status_code == 200
    assert response.json()["result"]["structuredContent"]["files"] == ["charts/harbor/values.yaml"]


def test_repo_search_dedupes_and_filters_noise(monkeypatch):
    monkeypatch.setattr(
        repo_search_tool.retrieval,
        "search_repo",
        lambda query, limit=5: {
            "repo_path": "/repo",
            "matches": [
                {"path": ".github/agents/check.agent.md", "snippet": "agent", "score": 0.8},
                {"path": "umbrella-helm-charts/tekton/values.yaml", "snippet": "yaml-1", "score": 1.2},
                {"path": "umbrella-helm-charts/tekton/values.yaml", "snippet": "yaml-2", "score": 1.1},
                {"path": "README.md", "snippet": "readme", "score": 0.9},
            ],
        },
    )

    result = repo_search_tool.search_repo("argocd", limit=5)

    assert ".github/agents/check.agent.md" not in result["files"]
    assert result["files"].count("umbrella-helm-charts/tekton/values.yaml") == 1


def test_repo_search_prioritizes_infra_files(monkeypatch):
    monkeypatch.setattr(
        repo_search_tool.retrieval,
        "search_repo",
        lambda query, limit=5: {
            "repo_path": "/repo",
            "matches": [
                {"path": "notes/architecture.md", "snippet": "md", "score": 0.4},
                {"path": "umbrella-helm-charts/tekton/Chart.yaml", "snippet": "chart", "score": 1.4},
            ],
        },
    )

    result = repo_search_tool.search_repo("tekton", limit=2)

    assert result["files"][0] == "umbrella-helm-charts/tekton/Chart.yaml"


# --- New retrieval tool tests ---


def test_read_file_slice_endpoint(monkeypatch):
    monkeypatch.setattr(main_module, "read_file_slice", lambda path, start_line=1, end_line=None, max_chars=2500: {
        "result": f"{path} lines 1-10 of 50.",
        "files": [path],
        "data": {"path": path, "start_line": 1, "end_line": 10, "total_lines": 50, "content": "line1\nline2"},
    })

    response = client.post("/read-file-slice", json={"path": "charts/harbor/values.yaml", "start_line": 1, "end_line": 10})

    assert response.status_code == 200
    assert response.json()["data"]["total_lines"] == 50


def test_find_related_files_endpoint(monkeypatch):
    monkeypatch.setattr(main_module, "find_related_files", lambda path, max_results=5: {
        "result": "Found 2 files related to values.yaml.",
        "files": ["charts/harbor/Chart.yaml", "charts/harbor/templates/deployment.yaml"],
        "data": {"anchor": path, "related": ["charts/harbor/Chart.yaml", "charts/harbor/templates/deployment.yaml"]},
    })

    response = client.post("/find-related-files", json={"path": "charts/harbor/values.yaml"})

    assert response.status_code == 200
    assert len(response.json()["files"]) == 2


def test_find_k8s_objects_endpoint(monkeypatch):
    monkeypatch.setattr(main_module, "find_k8s_objects", lambda kind=None, name=None, namespace=None, max_results=10: {
        "result": "Found 1 Kubernetes objects.",
        "files": ["gateway/route.yaml"],
        "data": {"objects": [{"kind": "HTTPRoute", "name": "harbor", "namespace": "harbor", "file": "gateway/route.yaml"}]},
    })

    response = client.post("/find-k8s-objects", json={"kind": "HTTPRoute"})

    assert response.status_code == 200
    assert response.json()["data"]["objects"][0]["kind"] == "HTTPRoute"


# --- New summarization tool tests ---


def test_summarize_files_endpoint(monkeypatch):
    monkeypatch.setattr(main_module, "summarize_files", lambda paths, max_chars_per_file=1500, total_budget=8000: {
        "result": "Summarized 1 files.",
        "files": paths,
        "data": {"summaries": [{"path": paths[0], "lines": 42, "chars": 1200, "type": "yaml"}]},
    })

    response = client.post("/summarize-files", json={"paths": ["charts/harbor/values.yaml"]})

    assert response.status_code == 200
    assert response.json()["data"]["summaries"][0]["lines"] == 42


def test_compress_logs_endpoint(monkeypatch):
    monkeypatch.setattr(main_module, "compress_logs", lambda log_text, max_chars=3000: {
        "result": "Detected argocd log patterns with 1 signal(s).",
        "files": [],
        "data": {"log_type": "argocd", "signals": ["ArgoCD sync failure"], "suggestions": ["Check status"], "excerpt": "error line"},
    })

    response = client.post("/compress-logs", json={"log_text": "argocd sync failed"})

    assert response.status_code == 200
    assert response.json()["data"]["log_type"] == "argocd"


def test_prepare_copilot_brief_endpoint(monkeypatch):
    monkeypatch.setattr(main_module, "prepare_copilot_brief", lambda question, findings=None, affected_files=None, likely_cause=None, verbosity="compact": {
        "result": f"## Question\n{question}\n\n## Action Needed\nAnalyze the above findings and suggest the fix.",
        "files": affected_files or [],
        "data": {"question": question, "findings": findings or [], "affected_files": affected_files or [], "likely_cause": likely_cause or "", "verbosity": verbosity},
    })

    response = client.post("/prepare-copilot-brief", json={
        "question": "Why does ingress fail?",
        "findings": ["HTTPRoute missing parentRefs"],
        "affected_files": ["gateway/route.yaml"],
        "likely_cause": "Missing gateway reference",
    })

    assert response.status_code == 200
    assert "ingress fail" in response.json()["data"]["question"]
    assert response.json()["data"]["likely_cause"] == "Missing gateway reference"


def test_mcp_tool_call_compress_logs(monkeypatch):
    monkeypatch.setattr(main_module.mcp_server, "compress_logs", lambda log_text, max_chars=3000: {
        "result": "Detected argocd log patterns with 1 signal(s).",
        "files": [],
        "data": {"log_type": "argocd", "signals": ["sync failure"], "suggestions": ["check status"], "excerpt": "err"},
    })
    main_module.mcp_server.TOOLS["compress_logs"]["handler"] = lambda args: main_module.mcp_server.compress_logs(args["log_text"], max_chars=args.get("max_chars", 3000))

    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "compress_logs", "arguments": {"log_text": "argocd sync failed"}},
        },
    )

    assert response.status_code == 200
    assert "argocd" in response.json()["result"]["structuredContent"]["data"]["log_type"]


def test_mcp_tool_call_prepare_copilot_brief(monkeypatch):
    monkeypatch.setattr(main_module.mcp_server, "prepare_copilot_brief", lambda question, findings=None, affected_files=None, likely_cause=None, verbosity="compact": {
        "result": f"## Question\n{question}",
        "files": affected_files or [],
        "data": {"question": question, "findings": findings or [], "affected_files": affected_files or [], "likely_cause": likely_cause or ""},
    })
    main_module.mcp_server.TOOLS["prepare_copilot_brief"]["handler"] = lambda args: main_module.mcp_server.prepare_copilot_brief(
        question=args["question"], findings=args.get("findings"), affected_files=args.get("affected_files"), likely_cause=args.get("likely_cause"), verbosity=args.get("verbosity", "compact"),
    )

    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {"name": "prepare_copilot_brief", "arguments": {"question": "Why ingress fails?", "findings": ["missing ref"], "affected_files": ["route.yaml"]}},
        },
    )

    assert response.status_code == 200
    assert "ingress" in response.json()["result"]["content"][0]["text"]


# --- Cache tests ---


def test_cache_hit_and_miss():
    from app.cache import ContentCache

    cache = ContentCache(max_size=2)
    key = cache.key("test", "input")
    assert cache.get(key) is None
    assert cache.misses == 1

    cache.put(key, {"result": "cached"})
    assert cache.get(key) == {"result": "cached"}
    assert cache.hits == 1


def test_cache_eviction():
    from app.cache import ContentCache

    cache = ContentCache(max_size=2)
    cache.put("a", 1)
    cache.put("b", 2)
    cache.put("c", 3)  # evicts "a"
    assert cache.get("a") is None
    assert cache.get("b") == 2
    assert cache.get("c") == 3


# --- Smart preview test ---


def test_smart_preview():
    from app.tools.file_summarizer import _smart_preview

    short = "hello world"
    assert _smart_preview(short, 100) == short

    long_content = "A" * 500 + "B" * 500
    preview = _smart_preview(long_content, 200)
    assert len(preview) <= 250  # some overhead from separator
    assert "omitted" in preview


# --- Verbosity test ---


def test_copilot_brief_verbosity():
    from app.tools.copilot_brief import prepare_copilot_brief

    compact = prepare_copilot_brief(question="test", findings=["f1"] * 50, verbosity="compact")
    detailed = prepare_copilot_brief(question="test", findings=["f1"] * 50, verbosity="detailed")
    assert compact["data"]["verbosity"] == "compact"
    assert detailed["data"]["verbosity"] == "detailed"

