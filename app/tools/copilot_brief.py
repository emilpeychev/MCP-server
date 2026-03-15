from __future__ import annotations

VERBOSITY_LIMITS = {"compact": 500, "normal": 1500, "detailed": 5000}


def prepare_copilot_brief(
    question: str,
    findings: list[str] | None = None,
    affected_files: list[str] | None = None,
    likely_cause: str | None = None,
    verbosity: str = "compact",
    # New diagnostic fields
    detected_pattern: str | None = None,
    confidence: float | None = None,
    relevant_resources: list[str] | None = None,
    checks_performed: list[str] | None = None,
    missing_evidence: list[str] | None = None,
    recommended_next_step: str | None = None,
    ask_copilot: str | None = None,
    past_causes: list[str] | None = None,
) -> dict:
    """Build a structured, distilled brief for Copilot. This is the final handoff tool.

    Call this after retrieval and summarization to package everything
    Copilot needs in one compact payload — now including diagnostic context.
    """
    findings = findings or []
    affected_files = affected_files or []
    relevant_resources = relevant_resources or []
    checks_performed = checks_performed or []
    missing_evidence = missing_evidence or []
    past_causes = past_causes or []
    max_chars = VERBOSITY_LIMITS.get(verbosity, VERBOSITY_LIMITS["compact"])

    sections: list[str] = []

    # Problem + pattern
    sections.append(f"## Problem\n{question}")
    if detected_pattern:
        conf_str = f" ({confidence:.0%} confidence)" if confidence is not None else ""
        sections.append(f"## Detected Pattern\n{detected_pattern}{conf_str}")

    if affected_files:
        sections.append(f"## Affected Files\n" + "\n".join(f"- {f}" for f in affected_files))
    if relevant_resources:
        sections.append(f"## Relevant Resources\n" + "\n".join(f"- {r}" for r in relevant_resources))
    if findings:
        sections.append(f"## Key Findings\n" + "\n".join(f"- {f}" for f in findings))
    if likely_cause:
        sections.append(f"## Likely Cause\n{likely_cause}")
    if past_causes:
        sections.append(f"## Past Root Causes (from history)\n" + "\n".join(f"- {c}" for c in past_causes))
    if checks_performed:
        sections.append(f"## Checks Performed\n" + "\n".join(f"- {c}" for c in checks_performed))
    if missing_evidence:
        sections.append(f"## Missing Evidence\n" + "\n".join(f"- {m}" for m in missing_evidence))
    if recommended_next_step:
        sections.append(f"## Recommended Next Step\n{recommended_next_step}")

    ask = ask_copilot or "Analyze the above findings, confirm the root cause, and suggest the fix."
    sections.append(f"## Ask Copilot\n{ask}")

    brief = "\n\n".join(sections)
    if len(brief) > max_chars:
        brief = brief[:max_chars] + "\n... [truncated]"

    return {
        "result": brief,
        "files": affected_files,
        "data": {
            "question": question,
            "detected_pattern": detected_pattern or "",
            "confidence": confidence,
            "findings": findings,
            "affected_files": affected_files,
            "relevant_resources": relevant_resources,
            "likely_cause": likely_cause or "",
            "checks_performed": checks_performed,
            "missing_evidence": missing_evidence,
            "recommended_next_step": recommended_next_step or "",
            "ask_copilot": ask,
            "past_causes": past_causes,
            "verbosity": verbosity,
        },
    }
