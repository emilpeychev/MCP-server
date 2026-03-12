# langchain

## Build up stack 
- Install the LLM model manually
  
```sh
docker compose up -d
sleep 3
docker exec ollama ollama pull llama3
docker exec ollama ollama pull codellama
```

The API listens on `8081` and exposes `/healthz`, `/ask`, `/fullcontext`, `/models`, and `/docs`.

The Ollama connection is configurable with `OLLAMA_MODEL`, `OLLAMA_BASE_URL`, `OLLAMA_TIMEOUT`, and `MAX_CONTEXT`.
# mps
# MCP-server
# MCP-server
# MCP-server
# MCP-server
# MCP-server
