from .. import retrieval
from ..cache import tool_cache


NOISE_PREFIXES = (".github/agents/",)
BOOST_SUFFIXES = (".yaml", ".yml", ".tf")
BOOST_FILENAMES = {"chart.yaml", "kustomization.yaml"}


def _is_noise_path(path: str) -> bool:
    lowered = path.lower()
    return lowered.startswith(NOISE_PREFIXES)


def _priority(match: dict) -> tuple[int, float]:
    path = str(match.get("path", ""))
    lowered_path = path.lower()
    score = float(match.get("score", 0.0))

    is_boosted = (
        lowered_path.endswith(BOOST_SUFFIXES)
        or lowered_path.endswith("/chart.yaml")
        or lowered_path.endswith("/kustomization.yaml")
        or lowered_path in BOOST_FILENAMES
    )
    return (0 if is_boosted else 1, score)


def _dedupe_by_path(matches: list[dict], limit: int) -> list[dict]:
    selected = []
    seen_paths = set()

    for match in sorted(matches, key=_priority):
        path = str(match.get("path", ""))
        if not path or path in seen_paths or _is_noise_path(path):
            continue
        seen_paths.add(path)
        selected.append(match)
        if len(selected) >= limit:
            break
    return selected


def search_repo(query: str, limit: int = 5) -> dict:
    cache_key = tool_cache.key("search_repo", query, str(limit))
    cached = tool_cache.get(cache_key)
    if cached is not None:
        return cached

    overfetch = max(limit * 4, limit)
    search_result = retrieval.search_repo(query=query, limit=overfetch)
    matches = _dedupe_by_path(search_result.get("matches", []), limit=limit)

    search_result["matches"] = matches
    files = [match["path"] for match in matches]
    result = f"Found {len(matches)} repository matches."
    output = {"result": result, "files": files, "data": search_result}

    tool_cache.put(cache_key, output)
    return output