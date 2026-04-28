from __future__ import annotations

from pathlib import Path


class RepoContextReader:
    """Read-only repository context adapter for safe patch generation."""

    def __init__(self, repo_root: Path) -> None:
        self._repo_root = repo_root

    def list_candidate_files(self, *, limit: int = 30) -> list[str]:
        files = [
            str(path.relative_to(self._repo_root)).replace("\\", "/")
            for path in self._repo_root.rglob("*")
            if path.is_file() and ".git" not in path.parts
        ]
        return sorted(files)[:limit]

    def read_file_excerpt(self, relative_path: str, *, max_chars: int = 4000) -> str:
        target = (self._repo_root / relative_path).resolve()
        if not str(target).startswith(str(self._repo_root.resolve())):
            raise ValueError("Path traversal is not allowed.")
        if not target.exists() or not target.is_file():
            return ""
        return target.read_text(encoding="utf-8", errors="ignore")[:max_chars]
