"""Project workspace path resolution.

Centralizes all filesystem paths derived from a Project so business code does
not have to infer paths from project names.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ..models import Project
from .config import Settings


WIKI_CATEGORY_DIRS: dict[str, str] = {
    "entity": "entities",
    "concept": "concepts",
    "analysis": "analyses",
    "source": "sources",
    "note": "notes",
}


@dataclass(frozen=True)
class ProjectWorkspace:
    """Resolved, safe filesystem locations for one knowledge-base project."""

    root: Path
    wiki_dir_name: str = "wiki"
    assets_dir_name: str = "assets"
    project: Optional[Project] = None

    @classmethod
    def from_project(cls, project: Project) -> "ProjectWorkspace":
        return cls(
            root=Path(project.root_path).expanduser().resolve(),
            wiki_dir_name=project.wiki_dir_name or "wiki",
            assets_dir_name=project.assets_dir_name or "assets",
            project=project,
        )

    @classmethod
    def default(cls, settings: Settings) -> "ProjectWorkspace":
        return cls(root=settings.project_dir("default").expanduser().resolve())

    @property
    def raw_dir(self) -> Path:
        return self.root / "raw"

    @property
    def wiki_dir(self) -> Path:
        return self.root / self.wiki_dir_name

    @property
    def assets_dir(self) -> Path:
        return self.wiki_dir / self.assets_dir_name

    @property
    def index_path(self) -> Path:
        return self.wiki_dir / "index.md"

    @property
    def log_path(self) -> Path:
        return self.wiki_dir / "log.md"

    def wiki_category_dir(self, category: str) -> Path:
        return self.wiki_dir / WIKI_CATEGORY_DIRS.get(category, "concepts")

    def ensure_dirs(self) -> None:
        """Create SageMate's project subdirectories without touching content."""
        for path in [
            self.raw_dir,
            self.raw_dir / "articles",
            self.raw_dir / "papers",
            self.raw_dir / "papers" / "originals",
            self.raw_dir / "notes",
            self.raw_dir / "files",
            self.raw_dir / "images",
            self.raw_dir / "voice",
            self.wiki_dir,
            self.assets_dir,
            *[self.wiki_dir / d for d in WIKI_CATEGORY_DIRS.values()],
        ]:
            path.mkdir(parents=True, exist_ok=True)

    def resolve_raw_child(self, rel_path: str) -> Path:
        return _resolve_child(self.raw_dir, rel_path)

    def resolve_wiki_child(self, rel_path: str) -> Path:
        return _resolve_child(self.wiki_dir, rel_path)


def _resolve_child(base: Path, rel_path: str) -> Path:
    base_resolved = base.expanduser().resolve()
    target = (base_resolved / rel_path).resolve()
    target.relative_to(base_resolved)
    return target


def validate_project_root(path_value: str) -> Path:
    """Normalize and validate a user-supplied project root directory."""
    raw = path_value.strip()
    if not raw:
        raise ValueError("知识库目录不能为空")

    root = Path(raw).expanduser().resolve()
    if str(root) == root.anchor:
        raise ValueError("不能将系统根目录作为知识库目录")
    if root.exists() and not root.is_dir():
        raise ValueError(f"路径不是目录: {root}")

    return root


async def workspace_for_active_project(store, settings: Settings) -> ProjectWorkspace:
    active = await store.get_active_project()
    if not active:
        active = await store.get_project_by_name("default")
    if active:
        return ProjectWorkspace.from_project(active)
    return ProjectWorkspace.default(settings)
