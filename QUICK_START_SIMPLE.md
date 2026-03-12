# What's Actually Happening Here

## The Simple Picture

```
Your Computer
├── Docker Container (runs MCP server + Ollama)
└── VS Code (runs Copilot Chat)
    └── Copilot Chat asks the MCP server for help
```

When you ask Copilot Chat something like "search the repo for HTTPRoute", Copilot says:
- "I need help, let me ask the MCP server"
- MCP server searches the local repo
- Returns results back to Copilot
- Copilot shows you the answer in chat

## The 3 Steps You Need

### Step 1: Start the Docker Container

Open Terminal and run:

```bash
cd /home/eepeychev/repos/MCP
docker compose up -d --build
sleep 5
docker exec ollama ollama pull qwen2.5-coder:7b
```

**Check it worked:**
```bash
curl http://127.0.0.1:8081/healthz
```

If you see `{"status":"ok"...}`, go to Step 2.

### Step 2: Tell VS Code About the MCP Server

1. In VS Code, press `Ctrl+Shift+P`
2. Type `MCP: List Servers`
3. You should see `local-infra-assistant` appear
4. Click "Trust" or "Enable"

**That's it.** VS Code is now connected to the container.

### Step 3: Ask Copilot to Use the Tools

Open Copilot Chat (`Ctrl+L`), and type:

```
Search this repo for HTTPRoute
```

Copilot will use the MCP server to search, then show you results.

Other things you can ask:
- `Inspect ArgoCD manifests for drift risks`
- `Review this YAML for issues: [paste YAML]`
- `Analyze this log: [paste log]`

---

## If Something Doesn't Work

**"Container won't start"**
```bash
docker compose ps
docker compose logs infra-assistant
```

**"VS Code doesn't show `local-infra-assistant` in MCP: List Servers"**
- Make sure container is running (see above)
- Close and reopen VS Code
- Try command again

**"Copilot Chat doesn't use MCP tools"**
- Make sure server is Trusted (step 2)
- Restart VS Code

---

That's all. You don't need to use curl or understand JSON-RPC or any of that. Just:
1. Run the container
2. Trust the server in VS Code
3. Talk to Copilot

Does that make more sense now?
