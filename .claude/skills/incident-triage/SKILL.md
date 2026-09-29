---
name: incident-triage
description: "Use to triage a live infrastructure incident: classify the problem, pull the matching playbook, gather pod/log/event evidence from the cluster, and record the issue for later recall. Trigger when asked to 'triage', 'debug prod', 'why is X failing/crashing/restarting', 'investigate an outage', or when a service is down/erroring. Runs through the local-infra MCP and cites evidence before concluding."
---

# /incident-triage

Turn a vague "something is broken" into a structured, evidence-cited incident report with a recommended fix — and persist it so the next occurrence is faster to resolve.

## Usage

```
/incident-triage "<symptom>"                 # triage from a free-text symptom
/incident-triage <service> [ns:<namespace>]  # triage a named service
/incident-triage --no-record                 # do not persist the finding
/incident-triage --help                      # print this Usage block and stop
```

If no argument is given, ask for the symptom or the affected service/namespace once, then proceed. Do not guess the target.

## Auth model

- `kubectl_*` tools shell out to the real binary and inherit the terminal's ambient AWS/EKS auth — no kubeconfig to mount, no login step here.
- Read `data.status`/`data.category` on every cluster call: `unavailable` = binary missing (tooling gap), `unverified`+`auth` = cluster/context error (surface real `stderr`, do not guess). All cluster access is **read-only**.

## Steps

Follow in order. Cite the tool output backing each conclusion.

### 1. Classify
- `classify_problem` on the symptom/service to bucket the incident (crashloop, image pull, OOM, routing, config, dependency, etc.).
- `query_history` for prior matching issues — if a past fix exists, lead with it.

### 2. Load the playbook
- `get_playbook` for the classified category. Follow its checklist as the investigation spine.

### 3. Gather evidence (scoped to the target)
- `kubectl_get_pods` — identify non-`Ready`/restarting pods.
- `kubectl_describe_pod` — events, probe failures, exit codes, image pull errors for each suspect pod.
- `kubectl_get_events` — recent namespace events (`field_selector` to narrow).
- `kubectl_logs` for current logs; `kubectl_logs_previous` for the last crashed container.
- `compress_logs` to distill large/noisy log output into signal before reasoning.

### 4. Correlate to source
- `search_repo` / `read_file_slice` — tie the failure to the declaring manifest/Helm values/config (image tag, resource limits, env, probe settings).

### 5. Report and persist
- Output: `Symptom → Classification → Evidence (cited) → Root cause → Recommended fix`.
- Mark severity and whether the root cause is confirmed vs suspected.
- `prepare_copilot_brief` for a shareable summary when useful.
- Unless `--no-record`, call `record_issue` so `query_history` can surface this next time.
- If any leg was `unavailable`/`unverified`, state which conclusions are incomplete — never present a partial triage as complete.

## Guardrails

- MCP-first; if a tool returns empty/fails, say so, then fall back.
- Evidence before conclusions — no root-cause claim without the tool output that proves it.
- Read-only cluster access; never mutate, scale, restart, or delete anything.
- Never fabricate logs or live state to fill a gap left by a failed call.
