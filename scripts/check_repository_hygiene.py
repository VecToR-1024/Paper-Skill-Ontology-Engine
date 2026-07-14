from __future__ import annotations

import argparse
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
IGNORED_DIRS = {".git", ".pytest_cache", "__pycache__", ".mypy_cache", ".ruff_cache"}
IGNORED_SUFFIXES = {".pyc", ".pyo"}
DEFAULT_FORBIDDEN_NAMES = ("tang" + "zhehao", "TANGZH" + "~1")
TEXT_SUFFIXES = {
    ".bib",
    ".cmd",
    ".css",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".md",
    ".ps1",
    ".py",
    ".tex",
    ".toml",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}
TEXT_FILENAMES = {".gitattributes", ".gitignore"}


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    kind: str

    def format(self) -> str:
        return f"{self.path}:{self.line}: {self.kind}"


PATH_PATTERNS = (
    (
        "windows_user_home",
        re.compile(r"(?i)(?:file:///)?[A-Z]:[\\/]+Users[\\/]+[^\\/\s\"'<>]+"),
    ),
    (
        "structured_windows_absolute_path",
        re.compile(
            r"(?i)(?:path|dir|root|file|source_pdf|project_dir)[\w-]*\s*[:=]\s*[\"']?"
            r"[A-Z]:[\\/]+(?![\\/])[^\r\n\"'<>]+"
        ),
    ),
    (
        "unix_user_home",
        re.compile(r"(?i)(?<![:/])/(?:Users|home)/[^/\s\"'<>]+"),
    ),
    (
        "temporary_absolute_path",
        re.compile(r"(?i)(?<![:/])/(?:tmp|var/tmp|private/tmp|workspace)/[^\s\"'<>]+"),
    ),
    (
        "structured_unc_path",
        re.compile(
            r"(?i)(?:path|dir|root|file|source_pdf|project_dir)[\w-]*\s*[:=]\s*[\"']?"
            r"\\\\[^\\/\s\"'<>]+[\\/]+[^\\/\s\"'<>]+"
        ),
    ),
)


SECRET_PATTERNS = (
    (
        "private_key",
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    ),
    ("anthropic_api_key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}")),
    ("openai_api_key", re.compile(r"\bsk-(?!ant-)[A-Za-z0-9_-]{20,}")),
    ("github_token", re.compile(r"\b(?:ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})")),
    ("gitlab_token", re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}")),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("google_api_key", re.compile(r"\bAIza[0-9A-Za-z_-]{30,}")),
    ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}")),
    ("stripe_live_key", re.compile(r"\bsk_live_[A-Za-z0-9]{16,}")),
    ("npm_token", re.compile(r"\bnpm_[A-Za-z0-9]{20,}")),
    (
        "credential_in_uri",
        re.compile(r"(?i)\b[A-Z][A-Z0-9+.-]*://[^/\s:@]+:[^/\s@]+@"),
    ),
)


def iter_repository_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*")):
        try:
            relative = path.relative_to(root)
        except ValueError:
            continue
        if any(part in IGNORED_DIRS for part in relative.parts):
            continue
        if path.suffix.lower() in IGNORED_SUFFIXES:
            continue
        if path.is_file() or path.is_symlink():
            yield path


def read_for_scan(path: Path) -> str:
    if path.is_symlink():
        return os.readlink(path)
    return path.read_bytes().decode("utf-8", errors="ignore")


def is_text_path(path: Path) -> bool:
    return path.suffix.lower() in TEXT_SUFFIXES or path.name in TEXT_FILENAMES


def line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def scan_repository(root: Path, forbidden_names: Iterable[str] = ()) -> list[Finding]:
    root = root.resolve()
    names = tuple(
        dict.fromkeys(
            name.casefold()
            for name in (*DEFAULT_FORBIDDEN_NAMES, *tuple(forbidden_names))
            if name and name.strip()
        )
    )
    findings: set[Finding] = set()

    for path in iter_repository_files(root):
        relative = path.relative_to(root).as_posix()
        relative_folded = relative.casefold()
        for name in names:
            if name in relative_folded:
                findings.add(Finding(relative, 1, "forbidden_name_in_path"))

        try:
            text = read_for_scan(path)
        except OSError:
            findings.add(Finding(relative, 1, "unreadable_file"))
            continue

        folded = text.casefold()
        for name in names:
            start = folded.find(name)
            while start >= 0:
                findings.add(Finding(relative, line_number(text, start), "forbidden_name"))
                start = folded.find(name, start + len(name))

        if is_text_path(path):
            for kind, pattern in PATH_PATTERNS:
                for match in pattern.finditer(text):
                    findings.add(Finding(relative, line_number(text, match.start()), kind))

        for kind, pattern in SECRET_PATTERNS:
            for match in pattern.finditer(text):
                findings.add(Finding(relative, line_number(text, match.start()), kind))

    return sorted(findings, key=lambda item: (item.path, item.line, item.kind))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scan a release tree for machine-specific paths, personal names, and high-confidence secrets."
    )
    parser.add_argument("root", nargs="?", default=str(ROOT), help="Repository or release tree to scan.")
    parser.add_argument(
        "--forbidden-name",
        action="append",
        default=[],
        help="Additional case-insensitive personal name or identifier to reject. May be repeated.",
    )
    args = parser.parse_args()

    findings = scan_repository(Path(args.root), forbidden_names=args.forbidden_name)
    if findings:
        print(f"repository hygiene check failed: {len(findings)} finding(s)")
        for finding in findings:
            print(finding.format())
        return 1

    print("repository hygiene check: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
