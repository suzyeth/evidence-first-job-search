"""Repository hygiene: no stray control characters in source, config or tests.

Shell-based edits have more than once turned an intended regex `\\b` into a literal backspace (0x08), which
silently breaks word-boundary matching. This catches that class of bug in CI.
"""
import glob
import os

from conftest import HERE

ROOT = os.path.dirname(HERE)
PATTERNS = ["scripts/*.py", "scripts/*.json", "tests/*.py", "tests/fixtures/*", "*.md", "references/*.md",
            "templates/*", ".github/workflows/*.yml", ".github/ISSUE_TEMPLATE/*.yml"]


def test_no_control_characters():
    offenders = []
    for pattern in PATTERNS:
        for path in glob.glob(os.path.join(ROOT, pattern)):
            with open(path, encoding="utf-8") as f:
                for number, line in enumerate(f, 1):
                    bad = [hex(ord(c)) for c in line if ord(c) < 32 and c not in "\n\t\r"]
                    if bad:
                        offenders.append(f"{os.path.relpath(path, ROOT)}:{number} {bad}")
    assert not offenders, "control characters found:\n" + "\n".join(offenders)


def test_hygiene_check_covers_the_scripts():
    assert len(glob.glob(os.path.join(ROOT, "scripts/*.py"))) >= 7
