"""Prepare a template merge without altering project-owned files."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile


def git(
    *args: str, check: bool = True, cwd: Path | None = None, data: bytes | None = None
) -> subprocess.CompletedProcess[bytes]:
    """Run Git without interpreting paths or refs as shell commands."""
    result = subprocess.run(["git", *args], cwd=cwd, input=data, capture_output=True, check=False)
    if check and result.returncode:
        raise RuntimeError(f"Git {args[0]} failed: {os.fsdecode(result.stderr).strip()}")
    return result


def paths(output: bytes) -> list[str]:
    """Decode NUL-delimited Git paths using the filesystem encoding."""
    return [os.fsdecode(path) for path in output.split(b"\0") if path]


def ignored_paths(candidates: list[str], ignore_file: Path, matcher: Path) -> set[str]:
    """Match only the sync ignore rules, independently of repository gitignore rules."""
    if not candidates:
        return set()
    payload = b"\0".join(os.fsencode(path) for path in candidates) + b"\0"
    result = git(
        "-c",
        f"core.excludesfile={ignore_file}",
        "check-ignore",
        "--no-index",
        "--stdin",
        "-z",
        check=False,
        cwd=matcher,
        data=payload,
    )
    if result.returncode not in (0, 1):
        raise RuntimeError(os.fsdecode(result.stderr).strip())
    return set(paths(result.stdout))


def restore_paths(candidates: set[str]) -> None:
    """Restore protected files to HEAD and remove protected upstream-only files."""
    for path in sorted(candidates):
        literal = f":(literal){path}"
        existed = git("cat-file", "-e", f"HEAD:{path}", check=False).returncode == 0
        if existed:
            git("restore", "--source=HEAD", "--staged", "--worktree", "--", literal)
            continue
        git("reset", "-q", "HEAD", "--", literal)
        target = Path(path)
        if target.is_absolute() or ".." in target.parts or any(parent.is_symlink() for parent in target.parents):
            raise RuntimeError(f"Cannot safely restore protected path: {path}")
        if target.is_symlink() or target.is_file():
            target.unlink()
        elif target.exists():
            raise RuntimeError(f"Cannot safely remove protected directory: {path}")


def prepare(source_ref: str, ignore_file: Path) -> None:
    """Merge the source and stage only changes allowed by the sync ignore file."""
    if not ignore_file.is_file():
        raise RuntimeError(f"Template sync ignore file does not exist: {ignore_file}")
    if git("status", "--porcelain=v1", "--untracked-files=all").stdout:
        raise RuntimeError("Template sync requires a clean disposable checkout")
    if git("ls-files", "--others", "--ignored", "--exclude-standard", "-z").stdout:
        raise RuntimeError("Template sync requires a checkout without ignored local files")
    git("rev-parse", "--verify", f"{source_ref}^{{commit}}")

    with tempfile.TemporaryDirectory(prefix="template-sync-ignore-") as directory:
        matcher = Path(directory)
        git("init", "--quiet", "--template=", cwd=matcher)
        merge = git(
            "-c",
            "merge.renames=false",
            "merge",
            "--squash",
            "--allow-unrelated-histories",
            "--strategy=recursive",
            source_ref,
            check=False,
        )
        conflicts = paths(git("diff", "--name-only", "--diff-filter=U", "-z").stdout)
        protected = ignored_paths(conflicts, ignore_file, matcher)
        unexpected = sorted(set(conflicts) - protected)
        if merge.returncode and (merge.returncode != 1 or not conflicts or unexpected):
            details = os.fsdecode(merge.stderr + merge.stdout).strip()
            raise RuntimeError(f"Template merge failed; unresolved paths: {unexpected}\n{details}")
        restore_paths(protected)
        if git("diff", "--name-only", "--diff-filter=U", "-z").stdout:
            raise RuntimeError("Template merge still has unresolved conflicts")

        git("add", "--all")
        changed = paths(git("diff", "--cached", "--name-only", "--no-renames", "-z").stdout)
        restore_paths(ignored_paths(changed, ignore_file, matcher))
        remaining = paths(git("diff", "--cached", "--name-only", "--no-renames", "-z").stdout)
        print(f"Prepared {len(remaining)} changed paths; protected paths were restored to HEAD.")


def main() -> int:
    """Run from the disposable checkout to be synchronized."""
    if len(sys.argv) != 3:
        print("Usage: template-sync-prepare <source-ref> <ignore-file>", file=sys.stderr)
        return 2
    try:
        ignore_file = Path(sys.argv[2]).resolve(strict=True)
        os.chdir(os.fsdecode(git("rev-parse", "--show-toplevel").stdout).strip())
        prepare(sys.argv[1], ignore_file)
    except (OSError, RuntimeError) as err:
        print(f"Template sync failed: {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
