"""Break check: break the code on purpose in three places and show which tests notice.

For each break:
  1. copy the repo into a temporary folder (the real code is never touched)
  2. change one line in the copy
  3. run the tests on the copy and list the ones that fail
A break that no test notices means a test is missing. (A hand-made version of "mutation testing".)

Run from the repo root:  python scripts/break_check.py
"""

import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
NOT_COPIED = shutil.ignore_patterns("venv", ".git", "*.db", "__pycache__", "results", ".pytest_cache")


@dataclass
class Break:
    what: str          # what the break does, in plain words
    file: str          # the file it changes
    real_line: str     # the line as it is
    broken_line: str   # the line after the break


BREAKS = [
    Break(what="the rule: escalate only when every check flags",
          file="app/core/escalation.py",
          real_line="all_passed = all(result.passed for result in results)",
          broken_line="all_passed = any(result.passed for result in results)"),
    Break(what="dates are read month-first",
          file="app/core/text_matching.py",
          real_line='date(full_year(int(match["year"])), int(match["month"]), int(match["day"]))',
          broken_line='date(full_year(int(match["year"])), int(match["day"]), int(match["month"]))'),
    Break(what="an identifier may match inside a longer one",
          file="app/core/text_matching.py",
          real_line='rf"(?<![A-Z0-9]){pattern}(?![A-Z0-9])"',
          broken_line='rf"(?<![A-Z0-9]){pattern}"'),
]


def copy_of_repo(folder: Path) -> Path:
    copy = folder / "repo"
    shutil.copytree(REPO, copy, ignore=NOT_COPIED)
    return copy


def apply(broken: Break, copy: Path) -> None:
    path = copy / broken.file
    source = path.read_text()
    if source.count(broken.real_line) != 1:
        sys.exit(f"Can't apply '{broken.what}': the line to change isn't in {broken.file} exactly once.")
    path.write_text(source.replace(broken.real_line, broken.broken_line))


def failing_tests(copy: Path) -> list[str]:
    """Run the tests in the copy; return the names of the ones that failed."""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--quiet", "--tb=no", "-rf", "-p", "no:cacheprovider"],
        cwd=copy, capture_output=True, text=True,
    )
    failed_lines = [line for line in result.stdout.splitlines() if line.startswith("FAILED ")]
    return [line.removeprefix("FAILED tests/").split(" - ")[0] for line in failed_lines]


def report(title: str, failed: list[str]) -> None:
    print(f"\n{title}\n  tests that failed: {len(failed)}")
    for test in failed:
        print(f"    {test}")


def main() -> None:
    with tempfile.TemporaryDirectory() as folder:
        report("Nothing broken (the code as it is)", failing_tests(copy_of_repo(Path(folder))))

    unnoticed = []
    for broken in BREAKS:
        with tempfile.TemporaryDirectory() as folder:
            copy = copy_of_repo(Path(folder))
            apply(broken, copy)
            failed = failing_tests(copy)
        report(f"Broken: {broken.what}", failed)
        if not failed:
            unnoticed.append(broken.what)

    if unnoticed:
        print(f"\n!! No test noticed: {'; '.join(unnoticed)}. A test is missing.")
        sys.exit(1)
    print("\nEvery break was noticed by at least one test.")


if __name__ == "__main__":
    main()
