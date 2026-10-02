# MCP-first policy for this workspace

When answering infrastructure, GitOps, Kubernetes, Helm, ArgoCD, logs, or repo-analysis questions:

1. Attempt MCP tools first.
2. Prefer this order: search_repo -> summarize_files/read_file_slice -> specialized tools (inspect_gateway, inspect_argocd, render_helm, review_yaml, compress_logs, runtime_environment_info, opentofu_validate, terraform_validate).
3. Cite evidence from tool output before conclusions.
4. If a tool fails or returns empty results, state that explicitly and then use fallback reasoning.
5. Do not skip MCP calls when the question depends on repository facts.

## Use the MCP skills

This workspace ships task-specific skills under `.claude/skills/`. When a request matches one of these workflows, read the skill's `SKILL.md` first and follow it, driving the work through the local-infra MCP tools:

- **incident-triage** (`.claude/skills/incident-triage/SKILL.md`) — triage a live incident: classify the problem, pull the matching playbook, gather pod/log/event evidence, and record the issue. Trigger: "triage", "debug prod", "why is X failing/crashing/restarting", outages.
- **drift-check** (`.claude/skills/drift-check/SKILL.md`) — detect drift between what the repo CLAIMS (docs), DECLARES (Helm/K8s/ArgoCD/Terraform), and what is LIVE (kubectl). Trigger: "is prod what we say/ship?", "find config/deploy drift", "audit the cluster against the repo".
- **gateway-audit** (`.claude/skills/gateway-audit/SKILL.md`) — audit north-south routing (Gateway API / Ingress) and trace routes to healthy backends. Trigger: "audit the gateway/ingress/routes", "why is this host 404/503", "check HTTPRoute wiring".
- **iac-preflight** (`.claude/skills/iac-preflight/SKILL.md`) — validate IaC/manifests before merge/apply (Terraform/OpenTofu validate+fmt+plan, Helm render, YAML review) into one pass/fail gate. Trigger: "preflight", "validate the IaC/manifests", "is this safe to merge/apply". Never applies changes.

Skill rules:
- Prefer the matching skill over ad-hoc tool calls; the skill defines the correct tool order and evidence requirements.
- Skills are read-only/analysis workflows — never apply, deploy, or mutate cluster or infra state.
- If no skill matches, fall back to the MCP-first policy above.
