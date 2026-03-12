# Local Infra Assistant

This service keeps FastAPI endpoints for automation while exposing repo-aware infrastructure tools through an MCP-compatible HTTP endpoint for editor clients.

Quick start guide for editor usage: [COPILOT_MCP_OLLAMA_GUIDE.md](COPILOT_MCP_OLLAMA_GUIDE.md)

## Architecture

VS Code Copilot continues using Ollama directly for chat and editing. This service adds retrieval, infra tooling, and MCP tool calls.

```text
VS Code Copilot
			|
			| MCP tools
			v
FastAPI + MCP Server
			|
			+-- retrieval (repo search / FAISS)
			+-- tools (Helm, YAML, GitOps checks)
			+-- LLM reasoning via Ollama (optional)
```

## API

The API listens on `8081` and exposes:

- `GET /healthz`
- `GET /models`
- `POST /search-repo`
- `POST /review-yaml`
- `POST /analyze-log`
- `POST /render-helm`
- `POST /inspect-argocd`
- `POST /inspect-gateway`
- `POST /ask-repo`
- `POST /mcp`

Legacy endpoints remain available:

- `POST /ask`
- `POST /fullcontext`

## Environment

- `OLLAMA_BASE_URL`: Ollama base URL
- `OLLAMA_MODEL`: model used for optional reasoning
- `OLLAMA_TIMEOUT`: timeout for Ollama calls
- `MAX_CONTEXT`: maximum context length accepted by context endpoints
- `REPO_PATH`: container path indexed by the retrieval module; in Docker Compose it defaults to `/repos/${TARGET_REPO_NAME:-MCP}`
- `HOST_REPO_ROOT`: host directory mounted read-only at `/repos`; defaults to `/home/eepeychev/repos`
- `TARGET_REPO_NAME`: repository name under `HOST_REPO_ROOT` to index; for example `cloud-enablement-gitops-infrastructure`

## Startup

```sh
cp .env.example .env
# Edit .env and set TARGET_REPO_NAME to the repo you want indexed.
# Example: TARGET_REPO_NAME=cloud-enablement-gitops-infrastructure
docker compose up -d --build
sleep 3
docker exec ollama ollama pull qwen2.5-coder:7b
```

The service indexes `REPO_PATH` on startup and serves MCP JSON-RPC requests through `POST /mcp`.

By default, Docker Compose mounts `/home/eepeychev/repos` into `/repos` and indexes `/repos/MCP`. To analyze a different repository under that same root, set `TARGET_REPO_NAME` before starting the stack.

Examples:

```sh
TARGET_REPO_NAME=cloud-enablement-gitops-infrastructure docker compose up -d --build
TARGET_REPO_NAME=another-gitops-repo docker compose up -d --build
```

For repeatable local setup, prefer storing those values in `.env` (copied from `.env.example`) instead of passing them inline.

`GET /healthz` also reports the active `repo_path`, which is the fastest way to confirm the container is indexing the intended repository.

## VS Code MCP Client

Workspace config is provided in [.vscode/mcp.json](.vscode/mcp.json). It points VS Code at the local HTTP MCP endpoint:

```json
{
	"servers": {
		"local-infra-assistant": {
			"type": "http",
			"url": "http://127.0.0.1:8081/mcp"
		}
	}
}
```

Start the service, then run `MCP: List Servers` in VS Code and trust the workspace server. The tools become available in Copilot Chat once the server is started.

## Example MCP Calls

```json
{
	"jsonrpc": "2.0",
	"id": 1,
	"method": "tools/call",
	"params": {
		"name": "search_repo",
		"arguments": {
			"query": "Where is Harbor hostname defined?",
			"limit": 5
		}
	}
}
```

Available tools:

- `search_repo`
- `review_yaml`
- `render_helm`
- `analyze_log`
- `inspect_argocd`
- `inspect_gateway`

## End-To-End MCP Smoke Test

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
