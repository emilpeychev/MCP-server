# Copilot + MCP + Ollama Guide

This guide shows how to use GitHub Copilot in VS Code with this local MCP server and Ollama.

## What this setup gives you

- Copilot Chat for normal coding help
- MCP tools for repo-aware infra analysis
- Local model-backed reasoning through Ollama (used by this service)

## Prerequisites

- VS Code with GitHub Copilot and GitHub Copilot Chat extensions
- Docker and Docker Compose
- This repository cloned locally

## 1) Start the MCP + Ollama stack

```sh
cp .env.example .env
# Optional: point to a different repository on your host
# Example: HOST_REPO_PATH=/home/you/repos/cloud-enablement-gitops-infrastructure

docker compose up -d --build
```

Pull the model used by this service:

```sh
docker exec ollama ollama pull qwen2.5-coder:7b
```

## 2) Verify service health

```sh
curl -s http://127.0.0.1:8081/healthz
```

Expected: JSON with `"status":"ok"` and the active `repo_path`.

## 3) Connect VS Code to the MCP server

This workspace already includes MCP config in `.vscode/mcp.json`:

```json
{
  "servers": {
    "local-infra-assistant": {
      "type": "http",
      "url": "http://127.0.0.1:8081/mcp",
      "env": {
        "REPO_PATH": "/repos/*",
        "WORKSPACE_REPO_NAME": "${workspaceFolderBasename}",
        "OLLAMA_MODEL": "qwen2.5-coder:7b",
        "OLLAMA_BASE_URL": "http://ollama:11434"
      }
    }
  }
}
```

The `env` object above overrides matching values from `.env` for the running assistant service.

In VS Code:

1. Open this workspace folder.
2. Run command: `MCP: List Servers`.
3. Trust/enable `local-infra-assistant`.

## 3.5) Require MCP-first behavior in this workspace

To make Copilot attempt MCP tools before freeform reasoning, add workspace instructions.

Create `.github/copilot-instructions.md` with:

```md
# MCP-first policy for this workspace

When answering infrastructure, GitOps, Kubernetes, Helm, ArgoCD, logs, or repo-analysis questions:

1. Attempt MCP tools first.
2. Prefer this order: search_repo -> summarize_files/read_file_slice -> specialized tools (inspect_gateway, inspect_argocd, render_helm, review_yaml, compress_logs, runtime_environment_info, opentofu_validate, terraform_validate).
3. Cite evidence from tool output before conclusions.
4. If a tool fails or returns empty results, state that explicitly and then use fallback reasoning.
5. Do not skip MCP calls when the question depends on repository facts.
```

Notes:

- This is a strong policy and works well in practice, but it is not a protocol-level hard guarantee.
- Keep `local-infra-assistant` trusted in MCP server list.
- Verify behavior by asking: `Find the Harbor hostname and show source files.` You should see MCP tool calls.

## 4) Use MCP tools from Copilot Chat

Try prompts like:

- `Search this repo for HTTPRoute definitions and summarize risk areas.`
- `Inspect ArgoCD app manifests and list drift risks.`
- `Review this YAML for LoadBalancer and Gateway issues.`
- `Analyze this Tekton log and suggest likely root cause.`

Available tools exposed by this server:

- Retrieval: `search_repo`, `read_file_slice`, `find_related_files`, `find_k8s_objects`
- Summarization: `summarize_files`, `review_yaml`, `compress_logs`, `render_helm`, `inspect_argocd`, `inspect_gateway`, `prepare_copilot_brief`
- Diagnostic: `classify_problem`, `get_playbook`, `record_issue`, `query_history`
- Runtime and IaC stubs: `runtime_environment_info`, `kubectl_*`, `argocd_*`, `opentofu_*`, `terraform_*`

## 5) Quick MCP smoke test (optional)

List tools:

```sh
curl -s http://127.0.0.1:8081/mcp \
  -H 'content-type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

Call a tool:

```sh
curl -s http://127.0.0.1:8081/mcp \
  -H 'content-type: application/json' \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"search_repo","arguments":{"query":"Harbor hostname","limit":3}}}'
```

## Troubleshooting

- Copilot does not show MCP tools:
  - Ensure `docker compose ps` shows `infra-assistant` running.
  - Verify `.vscode/mcp.json` points to `http://127.0.0.1:8081/mcp`.
  - Re-run `MCP: List Servers` and trust the server.

- `ERR_CONNECTION_REFUSED` on port 8081:
  - Check if another process is using `8081`.
  - Restart stack: `docker compose up -d --force-recreate infra-assistant`.

- Wrong repository is being indexed:
  - For dynamic workspace selection, use `REPO_PATH=/repos/*` and set `WORKSPACE_REPO_NAME` in `.vscode/mcp.json` (for example `${workspaceFolderBasename}`).
  - Ensure `HOST_REPO_ROOT` (host parent folder with your repos) is mounted by Docker Compose.
  - Keep `HOST_REPO_PATH` set as a fallback single-repo target.
  - Recreate service: `docker compose up -d --build --force-recreate infra-assistant`.
  - Confirm with `curl http://127.0.0.1:8081/healthz`.

- Model errors:
  - Pull model again: `docker exec ollama ollama pull qwen2.5-coder:7b`.
  - Confirm service env uses the same model in `.env` via `OLLAMA_MODEL`.

If you asked for "ollala", this guide assumes you meant Ollama.
