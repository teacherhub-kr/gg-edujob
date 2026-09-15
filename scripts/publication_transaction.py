#!/usr/bin/env python3
"""Optimistic, non-force publication transaction for generated repository state.

The caller validates and stages a candidate against an immutable main SHA.  This
helper refuses to rebase generated snapshots across an unknown main change.  A
small allow-list may opt into replay, but only with an explicit revalidation
command against the new main.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import shlex
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Sequence


class PublicationError(RuntimeError):
    pass


@dataclass
class PublicationResult:
    state: str
    baseline_sha: str
    remote_sha: str
    candidate_commit: str | None = None
    attempts: int = 0
    changed_paths: tuple[str, ...] = ()
    reason: str = ""


def _run(
    args: Sequence[str],
    *,
    cwd: Path,
    check: bool = True,
    capture: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args),
        cwd=cwd,
        check=check,
        text=True,
        capture_output=capture,
    )


def _git(cwd: Path, *args: str, check: bool = True) -> str:
    result = _run(("git", *args), cwd=cwd, check=check)
    return (result.stdout or "").strip()


def capture_baseline(cwd: Path, output: Path) -> str:
    _git(cwd, "fetch", "origin", "main")
    local = _git(cwd, "rev-parse", "HEAD")
    remote = _git(cwd, "rev-parse", "origin/main")
    if local != remote:
        raise PublicationError(f"HEAD is not synchronized to origin/main: {local} != {remote}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(remote + "\n", encoding="utf-8")
    return remote


def _changed_paths(cwd: Path, old: str, new: str) -> tuple[str, ...]:
    if old == new:
        return ()
    return tuple(line for line in _git(cwd, "diff", "--name-only", old, new).splitlines() if line)


def _allowed(paths: Sequence[str], patterns: Sequence[str]) -> bool:
    return bool(patterns) and all(any(fnmatch.fnmatch(path, pattern) for pattern in patterns) for path in paths)


def _push_head(cwd: Path) -> bool:
    # Deliberately no --force/--force-with-lease: a newer main must win.
    return _run(("git", "push", "origin", "HEAD:main"), cwd=cwd, check=False).returncode == 0


def _write_status(path: Path | None, result: PublicationResult) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(result), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _replay_on_latest(
    cwd: Path,
    candidate: str,
    remote: str,
    revalidate: Callable[[], None],
) -> str:
    _git(cwd, "checkout", "-B", "publication-transaction", remote)
    cherry = _run(("git", "cherry-pick", candidate), cwd=cwd, check=False)
    if cherry.returncode != 0:
        _git(cwd, "cherry-pick", "--abort", check=False)
        raise PublicationError("candidate could not be replayed cleanly on latest main")
    revalidate()
    _git(cwd, "add", "-u")
    if _run(("git", "diff", "--cached", "--quiet"), cwd=cwd, check=False).returncode != 0:
        _git(cwd, "commit", "--amend", "--no-edit")
    return _git(cwd, "rev-parse", "HEAD")


def publish(
    cwd: Path,
    *,
    baseline_sha: str,
    message: str,
    status_path: Path | None = None,
    allow_concurrent_paths: Sequence[str] = (),
    revalidate: Callable[[], None] | None = None,
    max_attempts: int = 3,
) -> PublicationResult:
    cwd = cwd.resolve()
    baseline_sha = baseline_sha.strip()
    if not baseline_sha:
        raise PublicationError("baseline SHA is empty")
    if _git(cwd, "rev-parse", "HEAD") != baseline_sha:
        raise PublicationError("candidate HEAD moved away from its recorded baseline before commit")
    if _run(("git", "diff", "--cached", "--quiet"), cwd=cwd, check=False).returncode == 0:
        _git(cwd, "fetch", "origin", "main")
        result = PublicationResult("no-change", baseline_sha, _git(cwd, "rev-parse", "origin/main"))
        _write_status(status_path, result)
        return result

    _git(cwd, "commit", "-m", message)
    candidate = _git(cwd, "rev-parse", "HEAD")
    candidate_base = baseline_sha

    for attempt in range(1, max_attempts + 1):
        _git(cwd, "fetch", "origin", "main")
        remote = _git(cwd, "rev-parse", "origin/main")
        changed = _changed_paths(cwd, candidate_base, remote)
        if remote != candidate_base:
            if not (_allowed(changed, allow_concurrent_paths) and revalidate is not None):
                result = PublicationResult(
                    "superseded",
                    baseline_sha,
                    remote,
                    candidate,
                    attempt,
                    changed,
                    "origin/main changed after validation",
                )
                _write_status(status_path, result)
                return result
            try:
                candidate = _replay_on_latest(cwd, candidate, remote, revalidate)
            except (PublicationError, subprocess.CalledProcessError) as exc:
                result = PublicationResult(
                    "superseded", baseline_sha, remote, candidate, attempt, changed, str(exc)
                )
                _write_status(status_path, result)
                return result
            candidate_base = remote

        if not _push_head(cwd):
            continue

        _git(cwd, "fetch", "origin", "main")
        remote_after = _git(cwd, "rev-parse", "origin/main")
        reachable = _run(
            ("git", "merge-base", "--is-ancestor", candidate, "origin/main"),
            cwd=cwd,
            check=False,
        ).returncode == 0
        if not reachable:
            result = PublicationResult(
                "failed", baseline_sha, remote_after, candidate, attempt, (),
                "push returned success but candidate commit is not reachable from origin/main",
            )
            _write_status(status_path, result)
            raise PublicationError(result.reason)
        result = PublicationResult("published", baseline_sha, remote_after, candidate, attempt)
        _write_status(status_path, result)
        return result

    _git(cwd, "fetch", "origin", "main")
    remote = _git(cwd, "rev-parse", "origin/main")
    changed = _changed_paths(cwd, candidate_base, remote)
    result = PublicationResult(
        "superseded", baseline_sha, remote, candidate, max_attempts, changed,
        "non-force push lost the publication race",
    )
    _write_status(status_path, result)
    return result


def _command_revalidator(command: str, cwd: Path) -> Callable[[], None]:
    def run() -> None:
        result = subprocess.run(command, cwd=cwd, shell=True)
        if result.returncode != 0:
            raise PublicationError(f"latest-main revalidation failed: {shlex.split(command)[0]}")

    return run


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="action", required=True)
    capture = sub.add_parser("capture")
    capture.add_argument("--output", type=Path, required=True)

    pub = sub.add_parser("publish")
    pub.add_argument("--baseline-file", type=Path, required=True)
    pub.add_argument("--message", required=True)
    pub.add_argument("--status-file", type=Path)
    pub.add_argument("--allow-concurrent-path", action="append", default=[])
    pub.add_argument("--revalidate-command")
    pub.add_argument("--max-attempts", type=int, default=3)
    args = parser.parse_args(argv)
    cwd = Path.cwd()

    try:
        if args.action == "capture":
            print(capture_baseline(cwd, args.output))
            return 0
        baseline = args.baseline_file.read_text(encoding="utf-8").strip()
        callback = _command_revalidator(args.revalidate_command, cwd) if args.revalidate_command else None
        result = publish(
            cwd,
            baseline_sha=baseline,
            message=args.message,
            status_path=args.status_file,
            allow_concurrent_paths=args.allow_concurrent_path,
            revalidate=callback,
            max_attempts=args.max_attempts,
        )
        print(json.dumps(asdict(result), ensure_ascii=False))
        return 0
    except (PublicationError, subprocess.CalledProcessError) as exc:
        print(f"publication transaction failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
