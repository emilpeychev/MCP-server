from __future__ import annotations

import glob
import logging
import re
from dataclasses import dataclass
import os
from pathlib import Path

import faiss
import numpy as np

from .config import get_config_value

logger = logging.getLogger(__name__)

SUPPORTED_SUFFIXES = {".yaml", ".yml", ".md", ".tf", ".py"}
IGNORED_PARTS = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".venv", "node_modules"}
NOISE_RELATIVE_PREFIXES = (".github/agents/",)
EMBED_DIMENSION = 256
CHUNK_SIZE = 900
CHUNK_OVERLAP = 120


@dataclass
class ChunkRecord:
    path: str
    snippet: str


class RepoIndex:
    def __init__(self) -> None:
        self.repo_path = self._resolve_repo_path(get_config_value("REPO_PATH", "/repo"))
        self.index: faiss.IndexFlatL2 | None = None
        self.records: list[ChunkRecord] = []
        self.indexed_files = 0

    def rebuild(self, repo_path: str | Path | None = None) -> dict:
        if repo_path is not None:
            self.repo_path = self._resolve_repo_path(str(repo_path))

        self.records = []
        self.indexed_files = 0
        vectors: list[np.ndarray] = []

        for file_path in self._iter_repo_files():
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            if not content.strip():
                continue
            self.indexed_files += 1
            for chunk in self._chunk_text(content):
                self.records.append(ChunkRecord(path=str(file_path.relative_to(self.repo_path)), snippet=chunk))
                vectors.append(self._embed(chunk))

        self.index = faiss.IndexFlatL2(EMBED_DIMENSION)
        if vectors:
            matrix = np.vstack(vectors).astype("float32")
            self.index.add(matrix)
        return self.stats

    @property
    def stats(self) -> dict:
        return {"repo_path": str(self.repo_path), "indexed_files": self.indexed_files, "chunks": len(self.records)}

    def search(self, query: str, limit: int = 5) -> dict:
        if self.index is None:
            self.rebuild()

        if self.index is None or not self.records:
            return {"matches": [], "repo_path": str(self.repo_path)}

        search_limit = min(limit, len(self.records))
        query_vector = self._embed(query).reshape(1, -1).astype("float32")
        distances, indices = self.index.search(query_vector, search_limit)
        matches = []
        for distance, index in zip(distances[0], indices[0], strict=False):
            if index < 0:
                continue
            record = self.records[index]
            matches.append(
                {
                    "path": record.path,
                    "snippet": record.snippet,
                    "score": round(float(distance), 4),
                }
            )
        return {"matches": matches, "repo_path": str(self.repo_path)}

    def _iter_repo_files(self):
        if not self.repo_path.exists():
            return []
        paths = []
        for path in self.repo_path.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
                continue
            if any(part in IGNORED_PARTS for part in path.parts):
                continue
            relative_path = path.relative_to(self.repo_path).as_posix()
            if relative_path.startswith(NOISE_RELATIVE_PREFIXES):
                continue
            paths.append(path)
        return paths

    def _resolve_repo_path(self, configured_path: str) -> Path:
        raw_path = configured_path.strip() if configured_path else "/repo"
        if not raw_path:
            raw_path = "/repo"

        expanded_path = self._expand_workspace_tokens(raw_path)
        if not any(char in expanded_path for char in "*?[]"):
            return Path(expanded_path).resolve()

        matches = sorted(Path(candidate).resolve() for candidate in glob.glob(expanded_path) if Path(candidate).is_dir())
        if not matches:
            logger.warning("REPO_PATH pattern '%s' had no directory matches.", expanded_path)
            return Path(expanded_path).resolve()

        preferred_repo = self._get_workspace_repo_selector()
        if preferred_repo:
            preferred_name = Path(preferred_repo).name
            for candidate in matches:
                if candidate.name == preferred_name:
                    return candidate
            logger.warning(
                "No REPO_PATH match for workspace selector '%s'. Using first match '%s'.",
                preferred_name,
                matches[0],
            )

        if len(matches) > 1:
            logger.warning(
                "REPO_PATH pattern '%s' matched multiple repos (%s). Using '%s'. Set WORKSPACE_REPO_NAME to choose.",
                expanded_path,
                ", ".join(path.name for path in matches),
                matches[0],
            )
        return matches[0]

    def _expand_workspace_tokens(self, path_value: str) -> str:
        replacements = {
            "${workspaceFolderBasename}": self._get_workspace_repo_selector(),
            "${WORKSPACE_REPO_NAME}": self._get_workspace_repo_selector(),
        }

        expanded = path_value
        for token, value in replacements.items():
            if token in expanded and value:
                expanded = expanded.replace(token, value)
        return os.path.expandvars(expanded)

    def _get_workspace_repo_selector(self) -> str:
        selector = self._normalize_selector(get_config_value("WORKSPACE_REPO_NAME", "").strip())
        if selector:
            return selector

        selector = self._normalize_selector(get_config_value("TARGET_REPO_NAME", "").strip())
        if selector:
            return selector

        selector = os.getenv("WORKSPACE_REPO_NAME", "").strip()
        if selector:
            return selector

        host_repo_path = os.getenv("HOST_REPO_PATH", "").strip()
        if host_repo_path and host_repo_path not in {".", "./"}:
            return Path(host_repo_path).name

        return ""

    def _normalize_selector(self, selector: str) -> str:
        if selector.startswith("${") and selector.endswith("}"):
            return ""
        return selector

    def _chunk_text(self, content: str) -> list[str]:
        normalized = content.replace("\r\n", "\n")
        if len(normalized) <= CHUNK_SIZE:
            return [normalized]

        chunks = []
        start = 0
        while start < len(normalized):
            end = min(len(normalized), start + CHUNK_SIZE)
            chunks.append(normalized[start:end])
            if end == len(normalized):
                break
            start = max(end - CHUNK_OVERLAP, start + 1)
        return chunks

    def _embed(self, text: str) -> np.ndarray:
        vector = np.zeros(EMBED_DIMENSION, dtype="float32")
        tokens = re.findall(r"[a-zA-Z0-9_./-]+", text.lower())
        if not tokens:
            return vector
        for token in tokens:
            bucket = hash(token) % EMBED_DIMENSION
            vector[bucket] += 1.0
        norm = np.linalg.norm(vector)
        if norm > 0:
            vector /= norm
        return vector


_REPO_INDEX = RepoIndex()


def index_repo(path: str | Path | None = None) -> dict:
    return _REPO_INDEX.rebuild(path)


def search_repo(query: str, limit: int = 5) -> dict:
    return _REPO_INDEX.search(query, limit=limit)


def get_index_stats() -> dict:
    return _REPO_INDEX.stats

