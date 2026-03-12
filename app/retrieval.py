from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

import faiss
import numpy as np

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
        self.repo_path = Path(os.getenv("REPO_PATH", "/repo")).resolve()
        self.index: faiss.IndexFlatL2 | None = None
        self.records: list[ChunkRecord] = []
        self.indexed_files = 0

    def rebuild(self, repo_path: str | Path | None = None) -> dict:
        if repo_path is not None:
            self.repo_path = Path(repo_path).resolve()

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