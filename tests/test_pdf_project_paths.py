from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def read_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def write_text_pdf(path: Path) -> None:
    content = b"BT /F1 12 Tf 72 720 Td (Portable path test text.) Tj ET"
    objects = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>\nendobj\n",
        b"4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
        b"5 0 obj\n<< /Length " + str(len(content)).encode("ascii") + b" >>\nstream\n" + content + b"\nendstream\nendobj\n",
    ]
    document = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(document))
        document.extend(obj)
    xref_offset = len(document)
    document.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    document.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        document.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    document.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )
    path.write_bytes(document)


class PdfProjectPathTests(unittest.TestCase):
    def run_script(self, script: str, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPTS / script), *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )

    def test_pdf_ingest_records_paths_relative_to_external_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            pdf = temp_root / "source.pdf"
            write_text_pdf(pdf)
            project = temp_root / "external-project"
            ingested = self.run_script(
                "ingest_pdf_project.py",
                str(pdf),
                "--out-dir",
                str(project),
                "--paper-id",
                "P-external-path",
                "--title",
                "External Path Test",
            )
            self.assertEqual(ingested.returncode, 0, ingested.stdout + ingested.stderr)

            state = read_yaml(project / "state" / "paper.yml")
            artifacts = state["objects"]["Artifact"]
            for artifact in artifacts.values():
                path_value = artifact["path"]
                self.assertTrue(path_value.startswith("artifacts/"), path_value)
                self.assertTrue((project / path_value).exists(), path_value)

            extracted_id = next(
                artifact_id
                for artifact_id, artifact in artifacts.items()
                if artifact["artifact_type"] == "extracted_text_md"
            )
            proposals = project / "proposals" / "source-spans.yml"
            extracted = self.run_script(
                "extract_source_spans.py",
                str(project),
                extracted_id,
                "--out",
                str(proposals),
            )
            self.assertEqual(extracted.returncode, 0, extracted.stdout + extracted.stderr)
            self.assertTrue(proposals.exists())


if __name__ == "__main__":
    unittest.main()
