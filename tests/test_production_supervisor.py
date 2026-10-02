import unittest
from datetime import datetime, timedelta, timezone

from scripts.production_supervisor import (
    KST,
    PRIVATE_REFRESH_IDLE_ACTIONS,
    PRIVATE_REFRESH_TARGETS,
    PRODUCTION_EVENTS,
    TARGETS,
    WATCHDOG_WORKFLOW,
    change_after_failure,
    circuit_blocked,
    consecutive_real_failures,
    detect_source_anomalies,
    latest_verified_production_success,
    official_publication_lag,
    private_refresh_due,
    production_runs,
    registry_contract_status,
    recovery_fallback_available,
    unified_publication_stale,
    watchdog_schedule_lag,
)


def run(conclusion, hours_ago=0, status="completed"):
    now = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)
    when = (now - timedelta(hours=hours_ago)).isoformat().replace("+00:00", "Z")
    return {
        "status": status,
        "conclusion": conclusion,
        "updated_at": when,
    }


class ProductionSupervisorTests(unittest.TestCase):
    def test_verified_data_writers_chain_unified_publication(self):
        from pathlib import Path

        for path in (
            ".github/workflows/update-jobs.yml",
            ".github/workflows/recover-missing-jobs.yml",
        ):
            text = Path(path).read_text(encoding="utf-8")
            self.assertIn("actions: write", text)
            self.assertIn("Dispatch unified publication when canonical jobs advanced", text)
            self.assertIn("git log -1 --format=%ct origin/main -- jobs.json", text)
            self.assertIn("git log -1 --format=%ct origin/main -- unified_jobs.json", text)
            self.assertIn("unified-search.yml/runs?per_page=10", text)
            self.assertIn("unified-search.yml/dispatches", text)

    def test_unified_publication_stale_when_jobs_are_newer(self):
        jobs = datetime(2026, 9, 19, 7, 28, tzinfo=KST)
        unified = datetime(2026, 9, 10, 23, 58, tzinfo=KST)
        self.assertTrue(unified_publication_stale(jobs, unified))
        self.assertTrue(unified_publication_stale(jobs, None))
        self.assertFalse(unified_publication_stale(jobs, jobs))
        self.assertFalse(unified_publication_stale(None, unified))

    def test_registry_contract_requires_full_metro_source_network(self):
        registry = {
            "gyeonggi": {
                "central": {"url": "https://example.test/gyeonggi"},
                "supportOffices": [{} for _ in range(25)],
            },
            "seoul": {
                "central": {"url": "https://example.test/seoul"},
                "supportOffices": [{} for _ in range(11)],
            },
            "incheon": {
                "central": {
                    "url": "https://example.test/incheon",
                    "requiredBoards": [{"bbsId": "1981"}, {"bbsId": "1534"}],
                },
                "supportOffices": [],
            },
        }
        ok, details = registry_contract_status(registry, {"officialSourceCount": 39})
        self.assertTrue(ok)
        self.assertEqual(details["breakdown"], {"gyeonggi": 26, "seoul": 12, "incheon": 1})
        self.assertEqual(details["totalOfficialSources"], 39)
        self.assertEqual(details["reasons"], [])

    def test_registry_contract_rejects_missing_incheon_board(self):
        registry = {
            "gyeonggi": {
                "central": {"url": "https://example.test/gyeonggi"},
                "supportOffices": [{} for _ in range(25)],
            },
            "seoul": {
                "central": {"url": "https://example.test/seoul"},
                "supportOffices": [{} for _ in range(11)],
            },
            "incheon": {
                "central": {
                    "url": "https://example.test/incheon",
                    "requiredBoards": [{"bbsId": "1981"}],
                },
                "supportOffices": [],
            },
        }
        ok, details = registry_contract_status(registry, {"officialSourceCount": 39})
        self.assertFalse(ok)
        self.assertTrue(any("missing-required-boards=1534" in x for x in details["reasons"]))

    def test_registry_contract_rejects_published_count_mismatch(self):
        registry = {
            "gyeonggi": {
                "central": {"url": "https://example.test/gyeonggi"},
                "supportOffices": [{} for _ in range(25)],
            },
            "seoul": {
                "central": {"url": "https://example.test/seoul"},
                "supportOffices": [{} for _ in range(11)],
            },
            "incheon": {
                "central": {
                    "url": "https://example.test/incheon",
                    "requiredBoards": [{"bbsId": "1981"}, {"bbsId": "1534"}],
                },
                "supportOffices": [],
            },
        }
        ok, details = registry_contract_status(registry, {"officialSourceCount": 38})
        self.assertFalse(ok)
        self.assertTrue(any("officialSourceCount=38!=registry=39" in x for x in details["reasons"]))

    def test_latest_verified_production_success_accepts_recovery_path(self):
        status = {
            "fast": {"lastSuccessAt": "2026-09-20T07:00:00+09:00"},
            "recovery": {"lastSuccessAt": "2026-09-20T08:00:00+09:00"},
        }
        when, path = latest_verified_production_success(status)
        self.assertEqual(path, "recovery")
        self.assertEqual(when, datetime(2026, 9, 20, 8, 0, tzinfo=KST))

    def test_watchdog_schedule_lag_uses_ninety_minute_guard(self):
        now = datetime(2026, 9, 20, 12, 0, tzinfo=KST)
        self.assertFalse(watchdog_schedule_lag(now - timedelta(minutes=89), now))
        self.assertTrue(watchdog_schedule_lag(now - timedelta(minutes=91), now))
        self.assertTrue(watchdog_schedule_lag(None, now))

    def test_supervisor_treats_registry_changes_as_fast_revalidation_input(self):
        from pathlib import Path

        source = Path("scripts/production_supervisor.py").read_text(encoding="utf-8")
        self.assertIn('"sources.json",', source)

    def test_private_refresh_due_respects_source_age(self):
        now = datetime(2026, 9, 20, 12, 0, tzinfo=KST)
        self.assertTrue(private_refresh_due(None, now, 6))
        self.assertTrue(private_refresh_due(now - timedelta(hours=7), now, 6))
        self.assertFalse(private_refresh_due(now - timedelta(hours=5), now, 6))

    def test_artmore_candidate_freshness_uses_isolated_candidate_report(self):
        self.assertEqual(
            PRIVATE_REFRESH_TARGETS["private-artmore-candidate"]["report"],
            "artmore_reconciliation_report.candidate.json",
        )
        self.assertNotEqual(
            PRIVATE_REFRESH_TARGETS["private-artmore-candidate"]["report"],
            "artmore_reconciliation_report.json",
        )

    def test_artmore_promotion_compares_candidate_to_canonical_publication(self):
        from pathlib import Path

        source = Path("scripts/production_supervisor.py").read_text(encoding="utf-8")
        self.assertIn(
            'candidate_time = git_commit_time("artmore_reconciliation_report.candidate.json")',
            source,
        )
        self.assertIn(
            'canonical_artmore_time = git_commit_time("artmore_reconciliation_report.json")',
            source,
        )
        self.assertNotIn(
            'canonical_artmore_time = private_refresh_times.get("private-artmore-candidate")',
            source,
        )

    def test_artmore_collector_submits_verified_region_contract_directly(self):
        from pathlib import Path

        source = Path("scripts/crawl_artmore_browser.py").read_text(encoding="utf-8")
        block = source.split("async def establish_filter", 1)[1].split("async def page_rows", 1)[0]
        self.assertIn("array_area_type", block)
        self.assertIn("exclude_end_yn", block)
        self.assertIn("form.evaluate(\"f=>f.submit()\")", block)
        self.assertIn("direct region contract not preserved", block)
        self.assertNotIn('get_by_role("button", name="지역 선택")', block)

    def test_artmore_pagination_does_not_stop_on_postfilter_row_count(self):
        from pathlib import Path

        source = Path("scripts/crawl_artmore_browser.py").read_text(encoding="utf-8")
        self.assertNotIn("if len(rows) < 10:", source)
        self.assertIn("if not rows or not new_ids:", source)

    def test_private_overdue_can_use_safe_idle_and_backoff_slots(self):
        self.assertIn("recovery", PRIVATE_REFRESH_IDLE_ACTIONS)
        self.assertIn("completeness", PRIVATE_REFRESH_IDLE_ACTIONS)
        self.assertIn("skip-unified-circuit-open", PRIVATE_REFRESH_IDLE_ACTIONS)
        self.assertIn("skip-unified-backoff", PRIVATE_REFRESH_IDLE_ACTIONS)
        self.assertNotIn("fast", PRIVATE_REFRESH_IDLE_ACTIONS)
        self.assertNotIn("unified", PRIVATE_REFRESH_IDLE_ACTIONS)

    def test_github_run_history_queries_fail_closed(self):
        from pathlib import Path

        source = Path("scripts/production_supervisor.py").read_text(encoding="utf-8")
        block = source.split("def gh_runs", 1)[1].split("def git_commit_time", 1)[0]
        self.assertIn("check=True", block)

    def test_watchdog_rechecks_active_writer_immediately_before_dispatch(self):
        from pathlib import Path

        text = Path(".github/workflows/fast-refresh-watchdog.yml").read_text(encoding="utf-8")
        self.assertIn("Production workflow already active; no duplicate dispatch", text)
        self.assertIn('.event == "workflow_dispatch"', text)
        self.assertIn('.head_branch == "main"', text)
        self.assertIn('.status == "waiting"', text)

    def test_fast_active_slot_can_refresh_one_overdue_private_source(self):
        from pathlib import Path

        source = Path("scripts/production_supervisor.py").read_text(encoding="utf-8")
        self.assertIn('if set(active) == {"fast"}:', source)
        self.assertIn("choose_private_refresh_action(", source)
        self.assertIn(
            "Fast refresh is already active; using one isolated private refresh slot.",
            source,
        )

    def test_priority_contract_places_official_unified_backlog_before_fast(self):
        from pathlib import Path

        source = Path("scripts/production_supervisor.py").read_text(encoding="utf-8")
        unified_guard = source.index(
            "if unified_publication_stale(jobs_time, unified_time) and not fast_status_running:"
        )
        fast_guard = source.index("elif fast_needed and not fast_status_running:")
        self.assertLess(unified_guard, fast_guard)
        self.assertIn(
            "publish verified official jobs backlog before another Fast refresh",
            source,
        )

    def test_private_refresh_targets_are_dispatched_only_by_single_watchdog(self):
        from pathlib import Path

        watchdog = Path(".github/workflows/fast-refresh-watchdog.yml").read_text(encoding="utf-8")
        self.assertIn("startsWith(steps.gate.outputs.action, 'private-')", watchdog)
        for key, spec in PRIVATE_REFRESH_TARGETS.items():
            self.assertIn(f"{key}) workflow='{spec['workflow']}'", watchdog)
        self.assertIn("private-artmore-promote) workflow='promote-artmore.yml'", watchdog)

    def test_private_refresh_targets_keep_writer_workflows_dispatch_only(self):
        from pathlib import Path

        for spec in PRIVATE_REFRESH_TARGETS.values():
            text = Path(".github/workflows", spec["workflow"]).read_text(encoding="utf-8")
            trigger = text.split("permissions:", 1)[0]
            self.assertIn("workflow_dispatch:", trigger)
            self.assertNotIn("schedule:", trigger)
            self.assertNotIn("workflow_run:", trigger)

    def test_production_run_contract_excludes_pr_and_feature_branch_dispatch(self):
        now = datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc)
        runs = [
            {
                "id": 1,
                "event": "pull_request",
                "head_branch": "feature/x",
                "status": "in_progress",
                "created_at": (now - timedelta(minutes=1)).isoformat(),
                "run_started_at": (now - timedelta(minutes=1)).isoformat(),
            },
            {
                "id": 2,
                "event": "workflow_dispatch",
                "head_branch": "feature/x",
                "status": "completed",
                "conclusion": "success",
                "created_at": (now - timedelta(minutes=2)).isoformat(),
                "run_started_at": (now - timedelta(minutes=2)).isoformat(),
            },
            {
                "id": 3,
                "event": "workflow_dispatch",
                "head_branch": "main",
                "status": "completed",
                "conclusion": "failure",
                "created_at": (now - timedelta(minutes=3)).isoformat(),
                "run_started_at": (now - timedelta(minutes=3)).isoformat(),
            },
        ]
        kept = production_runs("unified-search.yml", runs)
        self.assertEqual([item["id"] for item in kept], [3])

    def test_rerun_started_at_controls_run_order(self):
        now = datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc)
        old_rerun = {
            "id": 10,
            "event": "workflow_dispatch",
            "head_branch": "main",
            "status": "completed",
            "conclusion": "success",
            "created_at": (now - timedelta(hours=8)).isoformat(),
            "run_started_at": (now - timedelta(minutes=2)).isoformat(),
        }
        newer_created_failure = {
            "id": 11,
            "event": "workflow_dispatch",
            "head_branch": "main",
            "status": "completed",
            "conclusion": "failure",
            "created_at": (now - timedelta(hours=1)).isoformat(),
            "run_started_at": (now - timedelta(hours=1)).isoformat(),
        }
        kept = production_runs("unified-search.yml", [newer_created_failure, old_rerun])
        self.assertEqual([item["id"] for item in kept], [10, 11])
        failures, _ = consecutive_real_failures(kept)
        self.assertEqual(failures, 0)

    def test_production_event_contract_is_explicit_for_every_writer(self):
        self.assertEqual(set(PRODUCTION_EVENTS), set(TARGETS.values()) | {WATCHDOG_WORKFLOW})
        for filename in TARGETS.values():
            self.assertEqual(PRODUCTION_EVENTS[filename], {"workflow_dispatch"})
        self.assertEqual(
            PRODUCTION_EVENTS[WATCHDOG_WORKFLOW],
            {"workflow_dispatch", "schedule"},
        )

    def test_official_publication_lag_triggers_after_three_hours(self):
        now = datetime(2026, 9, 29, 21, 0, tzinfo=KST)
        jobs = now - timedelta(hours=3, minutes=30)
        unified = jobs - timedelta(minutes=20)
        self.assertTrue(official_publication_lag(now, jobs, unified))
        self.assertFalse(
            official_publication_lag(now, now - timedelta(hours=2), unified)
        )
        self.assertFalse(official_publication_lag(now, jobs, jobs))
        self.assertFalse(official_publication_lag(now, None, unified))

    def test_supervisor_has_fast_failure_backoff_and_change_after_failure_probe(self):
        from pathlib import Path

        source = Path("scripts/production_supervisor.py").read_text(encoding="utf-8")
        self.assertIn("collector_contract_changed_after_failure", source)
        self.assertIn('action = "skip-fast-backoff"', source)
        self.assertIn("Unified is blocked but official collection is due", source)
        self.assertIn("unified_contract_changed_after_failure", source)

    def test_watchdog_does_not_cancel_in_progress_decision(self):
        from pathlib import Path

        text = Path(".github/workflows/fast-refresh-watchdog.yml").read_text(encoding="utf-8")
        self.assertIn("group: production-operations-watchdog", text)
        self.assertIn("cancel-in-progress: false", text)

    def test_cancelled_runs_do_not_count_as_failures(self):
        runs = [run("failure"), run("cancelled"), run("failure"), run("failure"), run("success")]
        count, _ = consecutive_real_failures(runs)
        self.assertEqual(count, 3)

    def test_success_resets_failure_streak(self):
        runs = [run("failure"), run("success"), run("failure"), run("failure")]
        count, _ = consecutive_real_failures(runs)
        self.assertEqual(count, 1)

    def test_fast_circuit_blocks_three_recent_real_failures(self):
        now = datetime(2026, 9, 16, 21, 0, tzinfo=KST)
        runs = [run("failure", 0), run("failure", 1), run("failure", 2), run("success", 3)]
        blocked, failures, _ = circuit_blocked("fast", runs, now)
        self.assertTrue(blocked)
        self.assertEqual(failures, 3)

    def test_code_change_allows_controlled_probe(self):
        now = datetime(2026, 9, 16, 21, 0, tzinfo=KST)
        runs = [run("failure", 0), run("failure", 1), run("failure", 2)]
        blocked, _, _ = circuit_blocked("fast", runs, now, allow_probe_after_change=True)
        self.assertFalse(blocked)

    def test_recovery_change_after_failure_allows_only_new_contract(self):
        failure_at = datetime(2026, 9, 18, 0, 59, tzinfo=KST)
        newer_contract = datetime(2026, 9, 18, 7, 42, tzinfo=KST)
        older_contract = datetime(2026, 9, 17, 23, 0, tzinfo=KST)
        self.assertTrue(change_after_failure(newer_contract, failure_at))
        self.assertFalse(change_after_failure(older_contract, failure_at))
        self.assertFalse(change_after_failure(None, failure_at))

    def test_recovery_circuit_allows_controlled_probe_after_change(self):
        now = datetime(2026, 9, 16, 21, 0, tzinfo=KST)
        runs = [run("failure", 0), run("failure", 1), run("failure", 2)]
        blocked, failures, _ = circuit_blocked(
            "recovery", runs, now, allow_probe_after_change=True
        )
        self.assertFalse(blocked)
        self.assertEqual(failures, 3)

    def test_recovery_fallback_available_when_no_recent_recovery_failure(self):
        now = datetime(2026, 9, 16, 21, 0, tzinfo=KST)
        runs = [run("success", 8)]
        available, reason, failures = recovery_fallback_available(runs, now)
        self.assertTrue(available)
        self.assertEqual(reason, "recovery-available")
        self.assertEqual(failures, 0)

    def test_recovery_fallback_respects_recent_failure_backoff(self):
        now = datetime(2026, 9, 16, 21, 0, tzinfo=KST)
        runs = [run("failure", 1), run("success", 5)]
        available, reason, failures = recovery_fallback_available(runs, now)
        self.assertFalse(available)
        self.assertEqual(reason, "recovery-recent-failure-backoff")
        self.assertEqual(failures, 1)

    def test_fast_circuit_has_recovery_failover_contract(self):
        from pathlib import Path

        source = Path("scripts/production_supervisor.py").read_text(encoding="utf-8")
        self.assertIn("production_stale_for_p0", source)
        self.assertIn("recovery_fallback_available(", source)
        self.assertIn("use Recovery as alternative verified production path on a fresh runner", source)

    def test_source_drop_is_conservative(self):
        previous = {
            "sources": [
                {"name": "A", "officialIdCount": 100, "coverageComplete": True},
                {"name": "B", "officialIdCount": 4, "coverageComplete": True},
            ]
        }
        current = {
            "sources": [
                {"name": "A", "officialIdCount": 10, "coverageComplete": True, "accessErrors": 0},
                {"name": "B", "officialIdCount": 0, "coverageComplete": True, "accessErrors": 0},
            ]
        }
        anomalies = detect_source_anomalies(current, previous)
        self.assertEqual([x["source"] for x in anomalies], ["A"])

    def test_incomplete_coverage_is_always_flagged(self):
        current = {
            "sources": [
                {"name": "A", "officialIdCount": 100, "coverageComplete": False, "accessErrors": 0},
                {"name": "B", "officialIdCount": 100, "coverageComplete": True, "accessErrors": 1},
            ]
        }
        anomalies = detect_source_anomalies(current, None)
        self.assertEqual({x["source"] for x in anomalies}, {"A", "B"})


if __name__ == "__main__":
    unittest.main()
