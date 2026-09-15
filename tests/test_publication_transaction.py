#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import publication_transaction as tx


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, text=True, capture_output=True
    ).stdout.strip()


class PublicationTransactionTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT)
        root = Path(self.temp.name)
        self.remote = root / "remote.git"
        self.seed = root / "seed"
        self.worker = root / "worker"
        self.other = root / "other"
        git(root, "init", "--bare", str(self.remote))
        git(root, "init", "-b", "main", str(self.seed))
        for repo in (self.seed,):
            git(repo, "config", "user.name", "test")
            git(repo, "config", "user.email", "test@example.com")
        (self.seed / "data.txt").write_text("baseline\n", encoding="utf-8")
        (self.seed / "diagnostic.json").write_text("{}\n", encoding="utf-8")
        git(self.seed, "add", ".")
        git(self.seed, "commit", "-m", "baseline")
        git(self.seed, "remote", "add", "origin", str(self.remote))
        git(self.seed, "push", "-u", "origin", "main")
        git(self.remote, "symbolic-ref", "HEAD", "refs/heads/main")
        for clone in (self.worker, self.other):
            git(root, "clone", str(self.remote), str(clone))
            git(clone, "config", "user.name", "test")
            git(clone, "config", "user.email", "test@example.com")
        self.status = root / "status.json"

    def tearDown(self):
        self.temp.cleanup()

    def advance_other(self, path: str, value: str):
        target = self.other / path
        target.write_text(value, encoding="utf-8")
        git(self.other, "add", path)
        git(self.other, "commit", "-m", f"advance {path}")
        git(self.other, "push", "origin", "main")

    def prepare_candidate(self) -> str:
        baseline_file = Path(self.temp.name) / "baseline.sha"
        baseline = tx.capture_baseline(self.worker, baseline_file)
        (self.worker / "data.txt").write_text("candidate\n", encoding="utf-8")
        git(self.worker, "add", "data.txt")
        return baseline

    def test_main_change_marks_candidate_superseded_without_publish(self):
        baseline = self.prepare_candidate()
        self.advance_other("data.txt", "newer-main\n")
        result = tx.publish(
            self.worker,
            baseline_sha=baseline,
            message="candidate",
            status_path=self.status,
        )
        self.assertEqual(result.state, "superseded")
        self.assertEqual((self.other / "data.txt").read_text(encoding="utf-8"), "newer-main\n")
        probe = Path(self.temp.name) / "probe"
        git(Path(self.temp.name), "clone", str(self.remote), str(probe))
        self.assertEqual((probe / "data.txt").read_text(encoding="utf-8"), "newer-main\n")
        self.assertEqual(json.loads(self.status.read_text())["state"], "superseded")

    def test_non_force_retry_revalidates_and_verifies_own_commit(self):
        baseline = self.prepare_candidate()
        original_push = tx._push_head
        calls = 0
        revalidated = []

        def racing_push(cwd: Path) -> bool:
            nonlocal calls
            calls += 1
            if calls == 1:
                self.advance_other("diagnostic.json", '{"newer": true}\n')
                return False
            return original_push(cwd)

        def revalidate():
            self.assertEqual((self.worker / "diagnostic.json").read_text(encoding="utf-8"), '{"newer": true}\n')
            self.assertEqual((self.worker / "data.txt").read_text(encoding="utf-8"), "candidate\n")
            revalidated.append(True)

        with mock.patch.object(tx, "_push_head", side_effect=racing_push):
            result = tx.publish(
                self.worker,
                baseline_sha=baseline,
                message="candidate",
                status_path=self.status,
                allow_concurrent_paths=("diagnostic.json",),
                revalidate=revalidate,
            )
        self.assertEqual(result.state, "published")
        self.assertEqual(result.attempts, 2)
        self.assertEqual(revalidated, [True])
        git(self.worker, "fetch", "origin", "main")
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", result.candidate_commit, "origin/main"],
            cwd=self.worker,
            check=True,
        )

    def test_success_without_reachability_is_failure(self):
        baseline = self.prepare_candidate()
        with mock.patch.object(tx, "_push_head", return_value=True):
            with self.assertRaises(tx.PublicationError):
                tx.publish(
                    self.worker,
                    baseline_sha=baseline,
                    message="candidate",
                    status_path=self.status,
                )
        self.assertEqual(json.loads(self.status.read_text())["state"], "failed")


if __name__ == "__main__":
    unittest.main()
