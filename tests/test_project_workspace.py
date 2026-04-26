from pathlib import Path

import pytest

from sagemate.core.project_workspace import (
    ProjectWorkspace,
    validate_project_root,
)
from sagemate.models import Project, ProjectCreate


def test_project_create_accepts_optional_root_path():
    payload = ProjectCreate(name="Research", root_path="/tmp/research-kb")

    assert payload.name == "Research"
    assert payload.root_path == "/tmp/research-kb"


def test_project_workspace_uses_project_root_path(tmp_path: Path):
    project = Project(id="p1", name="Research", root_path=str(tmp_path))
    workspace = ProjectWorkspace.from_project(project)

    assert workspace.root == tmp_path.resolve()
    assert workspace.raw_dir == tmp_path.resolve() / "raw"
    assert workspace.wiki_dir == tmp_path.resolve() / "wiki"
    assert workspace.assets_dir == tmp_path.resolve() / "wiki" / "assets"
    assert workspace.wiki_category_dir("concept") == tmp_path.resolve() / "wiki" / "concepts"


def test_project_workspace_ensure_dirs_creates_expected_structure(tmp_path: Path):
    workspace = ProjectWorkspace.from_project(
        Project(id="p1", name="Research", root_path=str(tmp_path))
    )

    workspace.ensure_dirs()

    for rel_path in [
        "raw/articles",
        "raw/papers/originals",
        "raw/notes",
        "raw/files",
        "raw/images",
        "raw/voice",
        "wiki/assets",
        "wiki/entities",
        "wiki/concepts",
        "wiki/analyses",
        "wiki/sources",
        "wiki/notes",
    ]:
        assert (tmp_path / rel_path).is_dir()


def test_project_workspace_rejects_raw_path_traversal(tmp_path: Path):
    workspace = ProjectWorkspace.from_project(
        Project(id="p1", name="Research", root_path=str(tmp_path))
    )

    with pytest.raises(ValueError):
        workspace.resolve_raw_child("../secrets.md")


def test_validate_project_root_rejects_files(tmp_path: Path):
    file_path = tmp_path / "not-a-dir.txt"
    file_path.write_text("x", encoding="utf-8")

    with pytest.raises(ValueError):
        validate_project_root(str(file_path))
