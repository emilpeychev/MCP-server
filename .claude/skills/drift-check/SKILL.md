---
name: drift-check
description: "Use to detect drift between what a repo CLAIMS (README/docs), what it DECLARES (Helm/Kubernetes/ArgoCD/Terraform manifests), and what is actually LIVE in the cluster (kubectl). Cross-checks all three layers via the local-infra MCP and returns an evidence-cited mismatch report. Trigger when asked 'is prod what we say/ship?', 'find config/deploy drift', 'audit the cluster against the repo', or after a deploy to verify reality matches intent."
---

# /drift-check

Compare three sources of truth for an infrastructure repo and report where they disagree:

1. **CLAIMED** — services, ports, endpoints, and hostnames described in `README.md` and docs.
2. **DECLARED** — the desired state in Helm charts, raw Kubernetes YAML, ArgoCD Applications, and Terraform/OpenTofu.
3. **LIVE** — the actual cluster topology from `kubectl` (and ArgoCD live resources).

`drift-check` is the one workflow that needs all three retrieval layers at once. Never answer it from a single source — always cite evidence from each leg before concluding.

## Usage

```
/drift-check                     # whole-repo audit against the whole cluster (default)
/drift-check <service>           # scope to one service/app (e.g. /drift-check payments-api)
/drift-check ns:<namespace>      # scope to one namespace
/drift-check --docs-only         # only CLAIMED vs DECLARED (no cluster access)
/drift-check --no-record         # do not persist findings via record_issue
/drift-check --help              # print this Usage block and stop
```

If no argument is given, default to a whole-repo, whole-cluster audit. If the corpus is large, first list candidate services and ask the user to narrow, rather than scanning everything blindly.

## Auth model (read this first)

- The MCP `kubectl_*` tools shell out to the real `kubectl` binary. They inherit the **ambient AWS/EKS credentials of the terminal the MCP runs in** — there is **no kubeconfig to mount** and **no login step** to perform inside this skill.
- Distinguish two failure modes and report them differently:
  - **Binary missing** (`kubectl not found` / non-zero from `shutil.which`): report the LIVE leg as **UNAVAILABLE** (tooling gap).
  - **Auth/API error** (non-zero exit with cluster stderr): report the LIVE leg as **UNVERIFIED** and surface the real `stderr`. Do **not** print the generic "mount a kubeconfig" hint, and do **not** guess live state.
- All cluster access is **read-only**. Never mutate the cluster. No `apply`, `scale`, `delete`, `patch`, or `rollout` — ever.

## Steps

Follow in order. Cite the tool output backing each finding.

### 1. Extract CLAIMED state (docs)
- Use `search_repo` to locate `README.md` and other docs.
- Use `read_file_slice` / `summarize_files` to pull concrete claims: service names, container ports, exposed endpoints, hostnames/routes, replica counts, images.
- Record each claim with its source file + line range.

### 2. Resolve DECLARED state (manifests)
- `find_k8s_objects` — enumerate declared K8s kinds (Deployment, Service, Ingress, Gateway, HTTPRoute, etc.).
- `render_helm` — render charts and compare the **rendered output**, never raw templates (values overrides change everything).
- `inspect_argocd` / `argocd_get_app` — treat ArgoCD Application spec as the desired state and note `syncPolicy`.
- `review_yaml` — sanity-check the manifests for structural issues that could explain drift.
- `terraform_validate` / `opentofu_validate` — if IaC is present, confirm it is valid before trusting its declarations.

### 3. Snapshot LIVE state (cluster)
Scope each call to the target service/namespace when one was given.
- `kubectl_get_pods` (+ `kubectl_describe_pod` for non-`Ready` pods)
- `kubectl_get_service`, `kubectl_get_endpoints`
- `kubectl_get_ingress`, `kubectl_get_gateway`, `kubectl_get_httproute`
- `argocd_get_app_resources` for the live tree ArgoCD sees.
- On any non-zero exit, apply the Auth-model rules above (UNAVAILABLE vs UNVERIFIED).

### 4. Diff into drift classes
Classify every mismatch:

| Class | Meaning |
|---|---|
| **Doc drift** | README claims a service/port/endpoint that no manifest declares (or vice versa). |
| **Deploy drift** | A manifest/Helm/ArgoCD resource is declared but not live, or live but not `Ready`. |
| **Config drift** | Declared image/replicas/port/env ≠ live values. |
| **Routing drift** | Gateway/HTTPRoute/Ingress hostnames disagree across README ↔ manifests ↔ live. |
| **Orphan drift** | A live resource has no manifest or doc source. |

Assign severity: **HIGH** (live ≠ declared, or missing prod resource), **MEDIUM** (declared ≠ documented), **LOW** (cosmetic/naming).

### 5. Report and persist
- Output a table: `Class | Resource | CLAIMED | DECLARED | LIVE | Severity | Evidence`.
- Every row cites the backing tool output (file+lines for repo legs, command for the live leg).
- Optionally call `classify_problem` to bucket the overall result and `prepare_copilot_brief` for a shareable summary.
- For each HIGH finding, call `record_issue` (unless `--no-record`) so the drift is queryable later via `query_history`.
- If any leg was UNAVAILABLE/UNVERIFIED, state which conclusions are therefore incomplete — never present a partial audit as complete.

## Guardrails

- MCP-first: attempt MCP tools before any raw shell reasoning; if a tool returns empty/fails, say so explicitly, then fall back.
- Evidence before conclusions — no drift claim without the tool output that proves it.
- Read-only cluster access only.
- Never fabricate live state to fill a gap left by a failed `kubectl` call.
