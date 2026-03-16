# MCP-first policy for this workspace

When answering infrastructure, GitOps, Kubernetes, Helm, ArgoCD, logs, or repo-analysis questions:

1. Attempt MCP tools first.
2. Prefer this order: search_repo -> summarize_files/read_file_slice -> specialized tools (inspect_gateway, inspect_argocd, render_helm, review_yaml, compress_logs, runtime_environment_info, opentofu_validate, terraform_validate).
3. Cite evidence from tool output before conclusions.
4. If a tool fails or returns empty results, state that explicitly and then use fallback reasoning.
5. Do not skip MCP calls when the question depends on repository facts.
