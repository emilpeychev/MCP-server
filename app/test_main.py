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
    assert response.json() == {"status": "ok", "repo_path": "/repo", "indexed_files": 3, "chunks": 7}


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
    assert response.json()["result"]["tools"]


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
    main_module.mcp_server.TOOLS["search_repo"]["handler"] = lambda arguments: main_module.mcp_server.search_repo(arguments["query"], limit=arguments.get("limit", 5))

    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "search_repo", "arguments": {"query": "Harbor hostname", "limit": 1}},
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

