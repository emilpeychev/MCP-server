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
        "REPO_PATH": "/repo",
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

## 4) Use MCP tools from Copilot Chat

Try prompts like:

- `Search this repo for HTTPRoute definitions and summarize risk areas.`
- `Inspect ArgoCD app manifests and list drift risks.`
- `Review this YAML for LoadBalancer and Gateway issues.`
- `Analyze this Tekton log and suggest likely root cause.`

Available tools exposed by this server:

- `search_repo`
- `review_yaml`
- `render_helm`
- `analyze_log`
- `inspect_argocd`
- `inspect_gateway`

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
  - Set `HOST_REPO_PATH` and `REPO_PATH` in `.env`.
  - Or override `REPO_PATH` in `.vscode/mcp.json` under `servers.local-infra-assistant.env`.
  - Recreate service: `docker compose up -d --build --force-recreate infra-assistant`.
  - Confirm with `curl http://127.0.0.1:8081/healthz`.

- Model errors:
  - Pull model again: `docker exec ollama ollama pull qwen2.5-coder:7b`.
  - Confirm service env uses the same model in `.env` via `OLLAMA_MODEL`.

If you asked for "ollala", this guide assumes you meant Ollama.
