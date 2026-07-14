from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from check_repository_hygiene import scan_repository  # noqa: E402


PERSONAL_NAME = "tang" + "zhehao"


def test_detects_personal_home_paths_and_names(tmp_path: Path) -> None:
    leak = tmp_path / "leak.yml"
    leak.write_text(
        "source: " + "C:" + "\\Users\\" + PERSONAL_NAME + "\\Documents\\paper.pdf\n",
        encoding="utf-8",
    )

    findings = scan_repository(tmp_path, forbidden_names=[PERSONAL_NAME])

    kinds = {finding.kind for finding in findings}
    assert "windows_user_home" in kinds
    assert "forbidden_name" in kinds


def test_detects_common_secret_shapes(tmp_path: Path) -> None:
    leak = tmp_path / "credentials.txt"
    leak.write_text("api_key=" + "sk-" + "A" * 32, encoding="utf-8")

    findings = scan_repository(tmp_path)

    assert {finding.kind for finding in findings} == {"openai_api_key"}


def test_accepts_relative_project_paths(tmp_path: Path) -> None:
    safe = tmp_path / "project.yml"
    safe.write_text(
        "artifact_path: artifacts/source.pdf\n"
        "output_dir: visualization\n"
        "secret_ref: env/SEMANTIC_SCHOLAR_API_KEY\n",
        encoding="utf-8",
    )

    assert scan_repository(tmp_path) == []


def test_repository_snapshot_has_no_machine_specific_paths_or_secrets() -> None:
    findings = scan_repository(ROOT, forbidden_names=[PERSONAL_NAME])

    assert not findings, "\n".join(finding.format() for finding in findings)
