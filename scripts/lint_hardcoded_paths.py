#!/usr/bin/env python3
"""Hardcoded absolute path linter for LAAP.

Scans Python files for hardcoded Windows/Unix absolute paths and reports
violations. Intended for use in CI to prevent new hardcoded paths from
being introduced after the path unification work in Phase 3.

Usage:
    python scripts/lint_hardcoded_paths.py [dir1 dir2 ...]

Default directories:
    laap/ tests/ demos/ scripts/development/

Exit codes:
    0 — no violations
    1 — violations found
    2 — bad arguments or unexpected error

Whitelist support:
    - Test fixtures (files under tests/ or named test_*.py / *_test.py)
    - Docstrings
    - Configuration modules (e.g. laap/config/paths.py)
    - Lines ending with ``# lint-hardcoded-ignore``
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

# Windows absolute paths like C:\..., D:/...
_WINDOWS_PATH_RE = re.compile(
    r"(?<![:/])[A-Za-z]:[\\/][^\s\"',:;]*[^\s\"',:;]?"
)

# Unix absolute paths like /home/..., /Users/..., /opt/..., /tmp/...
_UNIX_PATH_RE = re.compile(
    r"(?:^|[\s\"'=\(])"
    r"(/(?:home|Users|opt|tmp)/[^\s\"',:;]*)"
)

# URL schemes that may otherwise look like paths (e.g. file://D:/...)
_URL_SCHEME_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9+.-]*://")

# Placeholders / environment variable references we consider acceptable
_PLACEHOLDER_RE = re.compile(
    r"(%[A-Za-z_]+%|\{[A-Za-z_]+\}|\$[A-Za-z_]+|\$\{[A-Za-z_]+\})"
)

# Regex metacharacters that strongly suggest a string is a regex pattern rather
# than a concrete filesystem path.
_REGEX_METACHAR_RE = re.compile(r"[\*\+\?\|\^\$\(\)\[\]\{\}]")

# Minimum length for a Windows drive-letter path to avoid matching Python string
# escapes like \\n, \\t, \\s etc. (those are only 4 characters).
_MIN_WINDOWS_PATH_LEN = 5


def _is_config_module(path: Path) -> bool:
    """Configuration modules are allowed to reference concrete paths."""
    name = path.name.lower()
    parts = {p.lower() for p in path.parts}
    if name == "paths.py" or name in {"config.py", "settings.py", "constants.py"}:
        return True
    if "config" in parts or "settings" in parts:
        return True
    return False


def _is_test_fixture(path: Path) -> bool:
    """Test fixtures are allowed to use hardcoded paths for test data."""
    name = path.name.lower()
    parts = {p.lower() for p in path.parts}
    if "tests" in parts or "fixtures" in parts:
        return True
    if name.startswith("test_") or name.endswith("_test.py"):
        return True
    return False


def _line_is_docstring(line: str, in_docstring: bool, quote_char: str) -> Tuple[bool, str]:
    """Return (still_in_docstring, quote_char) for the next line."""
    stripped = line.strip()
    if in_docstring:
        # Check whether the current docstring ends on this line.
        end_idx = stripped.find(quote_char)
        if end_idx != -1:
            # It might just be the closing quote; check if it reopens.
            rest = stripped[end_idx + len(quote_char) :].strip()
            if rest.startswith(("\"\"\"", "'''")):
                new_quote = rest[:3]
                return _line_is_docstring(rest[3:], True, new_quote)
            return False, ""
        return True, quote_char

    if stripped.startswith(("\"\"\"", "'''")):
        quote_char = stripped[:3]
        rest = stripped[3:]
        # Single-line docstring?
        if quote_char in rest:
            return False, ""
        return True, quote_char

    return False, ""


def _contains_hardcoded_path(line: str) -> List[str]:
    """Return list of hardcoded absolute path substrings found in line."""
    hits: List[str] = []
    text = line

    # Strip trailing comment for the ignore check is done separately; here we
    # keep the code body only so that comments don't contribute false hits.
    if "#" in text:
        text = text.split("#", 1)[0]

    if not text.strip():
        return hits

    # Windows paths
    for m in _WINDOWS_PATH_RE.finditer(text):
        candidate = m.group(0)
        # Skip placeholders and URL-like schemes.
        if _PLACEHOLDER_RE.search(candidate):
            continue
        if _URL_SCHEME_RE.search(candidate):
            continue
        # Skip Python string escapes (e.g. \\n, \\t, \\s) and regex fragments.
        if len(candidate) < _MIN_WINDOWS_PATH_LEN:
            continue
        if _REGEX_METACHAR_RE.search(candidate):
            continue
        hits.append(candidate)

    # Unix paths
    for m in _UNIX_PATH_RE.finditer(text):
        candidate = m.group(1)
        if _PLACEHOLDER_RE.search(candidate):
            continue
        hits.append(candidate)

    return hits


def _scan_file(path: Path) -> List[Tuple[int, str, List[str]]]:
    """Return violations for a single file as (line_no, line_text, paths)."""
    violations: List[Tuple[int, str, List[str]]] = []

    is_config = _is_config_module(path)
    is_fixture = _is_test_fixture(path)

    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        print(f"[ERROR] Cannot read {path}: {exc}", file=sys.stderr)
        return violations

    in_docstring = False
    docstring_quote = ""

    for line_no, raw_line in enumerate(content.splitlines(), start=1):
        # Track docstrings first, because a closing/opening quote can appear
        # anywhere on the line.
        in_docstring, docstring_quote = _line_is_docstring(
            raw_line, in_docstring, docstring_quote
        )

        line = raw_line.rstrip("\n\r")

        # Explicit per-line opt-out
        if "# lint-hardcoded-ignore" in line:
            continue

        # Whitelisted contexts
        if is_config or is_fixture or in_docstring:
            continue

        hits = _contains_hardcoded_path(line)
        if hits:
            violations.append((line_no, line, hits))

    return violations


def _collect_python_files(dirs: Sequence[Path], exclude: Sequence[str]) -> List[Path]:
    """Collect .py files under dirs, excluding configured patterns."""
    files: List[Path] = []
    exclude_set = {s.strip().lower() for s in exclude}

    for directory in dirs:
        if not directory.exists():
            print(f"[WARN] Directory does not exist: {directory}", file=sys.stderr)
            continue
        for path in directory.rglob("*.py"):
            # Skip __pycache__ and hidden directories.
            if any(part.startswith(".") for part in path.parts):
                continue
            # Skip explicitly excluded directory names.
            if any(p.lower() in exclude_set for p in path.parts):
                continue
            files.append(path)

    # Deterministic order.
    files.sort(key=lambda p: str(p))
    return files


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Lint Python files for hardcoded absolute paths."
    )
    parser.add_argument(
        "directories",
        nargs="*",
        help="Directories to scan (default: laap tests demos scripts/development).",
    )
    parser.add_argument(
        "--exclude",
        default="legacy,__pycache__,.venv,node_modules,.git,_archive,external",
        help="Comma-separated directory names to exclude from scanning.",
    )
    args = parser.parse_args(argv)

    dirs: List[Path]
    if args.directories:
        dirs = [Path(d) for d in args.directories]
    else:
        dirs = [
            Path("laap"),
            Path("tests"),
            Path("demos"),
            Path("scripts/development"),
        ]

    # Resolve relative to the current working directory.
    dirs = [d.resolve() for d in dirs]

    exclude_names = [name.strip() for name in args.exclude.split(",") if name.strip()]
    files = _collect_python_files(dirs, exclude_names)

    total_violations = 0
    for path in files:
        violations = _scan_file(path)
        if not violations:
            continue
        # Print path relative to CWD for compactness.
        try:
            display_path = path.relative_to(Path.cwd())
        except ValueError:
            display_path = path
        for line_no, line, hits in violations:
            total_violations += 1
            print(f"{display_path}:{line_no}: {', '.join(hits)}")
            # Show the actual line content indented for context.
            print(f"    {line.strip()}")

    print(f"\nTotal hardcoded absolute path violations: {total_violations}")
    return 1 if total_violations else 0


if __name__ == "__main__":
    sys.exit(main())
