from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from ingest_paper_project import SourceInfo, default_out_dir  # noqa: E402


def test_default_output_is_a_sibling_project(tmp_path: Path) -> None:
    source_root = tmp_path / "paper-source"
    manuscript = source_root / "paper.tex"
    source = SourceInfo(manuscript, source_root, manuscript, "latex")

    assert default_out_dir(source) == tmp_path / "paper_ingested"


def test_artifact_manuscript_keeps_its_existing_project_root(tmp_path: Path) -> None:
    project_root = tmp_path / "paper-project"
    manuscript = project_root / "artifacts" / "manuscript.md"
    source = SourceInfo(manuscript, project_root, manuscript, "markdown")

    assert default_out_dir(source) == project_root
