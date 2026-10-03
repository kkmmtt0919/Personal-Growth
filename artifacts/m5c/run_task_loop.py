"""M5-c 冒烟：任务提交闭环（TaskLoop）—— offline / real + 证据产物。

模式（用户 2026-10-03 冻结，`M5-PLAN.md` §6/§12）：

* **offline**（默认）：FakeGateway 对例 —— 主链（提交 → 证据 → claim → 绑定 → 重评 → 归因）、
  probe 路径、archive 路径、`binding_missed`、失败留 active + 重跑幂等、三联条件守卫、
  数据边界；全部不联网、不调用模型。
* **real**（需 `M5_ALLOW_REAL_MODEL=1` 或 `M4_ALLOW_REAL_MODEL=1`）：**绑定为真实模型调用，
  ≤1 HTTP**（零额外重试、fail-stop）。任务生成本步用离线对例（真实生成已在 M5-b 验证）；
  G5（生成 + 绑定全真实，≤3 HTTP）在 M5-d。

数据边界：真实库只读对锚；实验库跑完即删；提交物为受控构造并如实标注
（本冒烟验证的是闭环机制，不是"用户本人完成了任务"）。
"""

from __future__ import annotations

import argparse
import asyncio
import gc
import hashlib
import json
import os
import sqlite3
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "backend"))
sys.path.insert(0, str(REPO / "tests"))

from growth_os.agent import FakeGateway
from growth_os.assessment import (
    BINDING_TASK,
    LoopGuardError,
    TaskLoop,
    build_loop_artifact,
    trace_task,
    verify_attribution,
    write_loop_artifact,
)
from growth_os.evidence import adapter
from growth_os.store import DELIVERABLE_EVIDENCE_TYPE, GrowthStore
from task_loop_fixtures import create_active_task, make_binding_proposer, seed_scenario

REAL_DB = REPO / "data" / "growth.db"
ANCHORS = REPO / "artifacts" / "m3a" / "evidence-anchors.json"
SUBMISSION_DIR = HERE / "submission"
GOAL_EXPECTED_TABLES = {
    "g_users",
    "g_goals",
    "g_goal_clarifications",
    "g_capabilities",
    "g_capability_claims",
    "g_assessments",
    "g_agent_runs",
    "g_gaps",
    "g_tasks",
    "g_task_submissions",
    "g_events",
}


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def anchor_check() -> dict:
    anchor = _load(ANCHORS)
    conn = sqlite3.connect(f"file:{REAL_DB.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    def digest(table: str) -> str:
        hasher = hashlib.sha256()
        for row in conn.execute(f"SELECT * FROM {table} ORDER BY rowid"):
            hasher.update(json.dumps(list(row), ensure_ascii=False, sort_keys=True).encode())
        return hasher.hexdigest()

    tables = tuple(anchor["table_content_sha256"])
    hashes = {table: digest(table) for table in tables}
    counts = {table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in tables}
    g_tables = sorted(
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'g_%'"
        ).fetchall()
    )
    conn.close()
    return {
        "content_hashes_match": all(hashes[t] == anchor["table_content_sha256"][t] for t in tables),
        "counts_match": counts == anchor["table_counts"],
        "g_tables_in_real_db": g_tables,
    }


class Scenario:
    """一次独立实验：自己的临时库 + 目录；跑完即关（不共享连接）。"""

    def __init__(self, workdir: Path, name: str, **seed_options):
        self.name = name
        self.workdir = workdir / name
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.db = self.workdir / f"{name}.db"
        self.db.unlink(missing_ok=True)
        self.store = GrowthStore(str(self.db))
        self.estore = adapter.open_store(self.db)
        self.scenario = seed_scenario(self.store, self.estore, self.workdir, **seed_options)

    def loop(self, gateway) -> TaskLoop:
        # 报告写入随产物归档的目录（不入 tmp）—— 归因产物里的 report_paths 必须可核对。
        return TaskLoop(
            store=self.store,
            evidence_store=self.estore,
            gateway=gateway,
            submission_dir=self.workdir / "submissions",
            report_directory=HERE / "reports" / self.name,
        )

    def fake_binding(self, **options) -> FakeGateway:
        return FakeGateway(
            responses={
                BINDING_TASK: make_binding_proposer(
                    path=self.scenario.get("capability_path"), **options
                )
            }
        )

    def close(self) -> None:
        self.estore.db.close()
        self.store.close()
        gc.collect()
        self.db.unlink(missing_ok=True)


def _artifact(workdir: Path, name: str, text: str) -> Path:
    target = workdir / name
    target.write_text(text, encoding="utf-8")
    return target


# ---------------------------------------------------------------------------
# 离线场景
# ---------------------------------------------------------------------------


def scenario_happy(workdir: Path) -> dict:
    case = Scenario(workdir, "happy")
    try:
        gap = case.scenario["gaps"]["practice"]
        task_id = create_active_task(case.store, gap)
        artifact = _artifact(
            case.workdir,
            "eval-set.md",
            "# 检索评测集（受控构造，如实标注）\n\n10 条样本与判定标准：\n1. …\n",
        )
        gateway = case.fake_binding()
        assert case.store.get_task(task_id)["status"] == "active"
        report = asyncio.run(case.loop(gateway).complete_task(task_id, artifact_path=artifact, note="离线冒烟"))
        attribution = report["attribution"]
        submission = case.store.list_task_submissions(task_id=task_id)
        claims = [
            entry
            for entry in adapter.claims_overview(case.estore)
            if (entry["claim"].get("metadata") or {}).get("growth_task_id") == task_id
        ]
        metadata = adapter.source_metadata(case.estore, attribution["submission"]["source_id"])
        gaps = {item["id"]: item for item in case.store.list_gaps(capability_id=case.scenario["capability"])}
        return {
            "checks": {
                "happy_status_level_changed": report["status"] == "level_changed",
                "happy_practice_3_to_4": (
                    attribution["before"]["practice"]["level"] == 3
                    and attribution["after"]["practice"]["level"] == 4
                ),
                "happy_gap_closed": gaps[gap["id"]]["status"] == "closed",
                "happy_understanding_gap_open": (
                    gaps[case.scenario["gaps"]["understanding"]["id"]]["status"] == "open"
                ),
                "happy_guard_all_true": all(attribution["guard"].values()),
                "happy_trace_complete": trace_task(
                    case.store, case.estore, task_id=task_id
                )["complete"],
                "happy_single_submission_and_claim": len(submission) == 1 and len(claims) == 1,
                "happy_source_metadata_frozen": (
                    metadata["growth_evidence_type"] == DELIVERABLE_EVIDENCE_TYPE["markdown"]
                    and metadata["growth_channel"] == "user_evidence"
                    and metadata["growth_attribution"] == "user_declared"
                    and metadata["growth_task_id"] == task_id
                ),
                "happy_one_binding_call": len(gateway.calls) == 1,
                "happy_done_is_terminal": case.store.get_task(task_id)["status"] == "done",
            },
            "detail": {
                "task_id": task_id,
                "gap_id": gap["id"],
                "status": report["status"],
                "before": attribution["before"],
                "after": attribution["after"],
                "closed_gap_ids": attribution["gaps"]["closed_gap_ids"],
                "binding": {
                    "provider": attribution["binding"]["provider"],
                    "model": attribution["binding"]["model"],
                    "accepted": attribution["binding"]["accepted_proposal_ids"],
                },
                "claim_id": attribution["claim"]["claim_id"],
                "guard": attribution["guard"],
                "report_paths": attribution["assessment"]["report_paths"],
            },
        }
    finally:
        case.close()


def scenario_probe(workdir: Path) -> dict:
    case = Scenario(workdir, "probe")
    try:
        gap = case.scenario["gaps"]["understanding"]
        task_id = create_active_task(
            case.store,
            gap,
            title="现场作答：RAG 检索流程五问",
            objective="产出一份现场作答记录，覆盖切分、向量化、召回、重排、评测五个环节",
            deliverable_type="probe_answer",
            acceptance_type="probe_rubric",
            acceptance="提交作答正文，按五个环节逐项核对要点是否完整",
        )
        report = asyncio.run(
            case.loop(case.fake_binding()).complete_task(
                task_id, probe_answer="一、切分：按语义段落切分……\n二、向量化：……\n"
            )
        )
        attribution = report["attribution"]
        gaps = {
            item["id"]: item
            for item in case.store.list_gaps(capability_id=case.scenario["capability"])
        }
        materialized = attribution["submission"]["materialized_path"]
        return {
            "checks": {
                "probe_evidence_type_is_probe_result": (
                    attribution["submission"]["evidence_type"] == "probe_result"
                ),
                "probe_understanding_2_to_3": (
                    attribution["before"]["understanding"]["level"] == 2
                    and attribution["after"]["understanding"]["level"] == 3
                ),
                "probe_gap_stays_open": gaps[gap["id"]]["status"] == "open",
                "probe_materialized_source": bool(materialized) and Path(materialized).is_file(),
                "probe_guard_all_true": all(attribution["guard"].values()),
            },
            "detail": {
                "task_id": task_id,
                "before": attribution["before"],
                "after": attribution["after"],
                "materialized_path": materialized,
            },
        }
    finally:
        case.close()


def scenario_archive(workdir: Path) -> dict:
    case = Scenario(workdir, "archive")
    try:
        gap = case.scenario["gaps"]["practice"]
        task_id = create_active_task(
            case.store,
            gap,
            title="搭建并调优一个可运行的最小 RAG 问答系统",
            objective="产出一个 ZIP 归档（含 README 与可运行脚本）",
            deliverable_type="archive",
            acceptance_type="test_run",
            acceptance="解压后一键运行，5 个测试问题均返回结果",
        )
        archive = case.workdir / "deliverable.zip"
        with zipfile.ZipFile(archive, "w") as bundle:
            bundle.writestr("a-small.md", "# 说明\n\n一句话。\n")
            bundle.writestr(
                "b-big.md",
                "# 主交付物\n\n"
                + "\n\n".join(f"第 {index} 段：检索评测说明。" for index in range(1, 12)),
            )
        report = asyncio.run(
            case.loop(case.fake_binding()).complete_task(task_id, artifact_path=archive)
        )
        submission = report["attribution"]["submission"]
        primary, other = submission["source_id"], next(
            item for item in submission["source_ids"] if item != submission["source_id"]
        )
        return {
            "checks": {
                "archive_two_sources_ingested": len(submission["source_ids"]) == 2,
                "archive_primary_is_richest": (
                    submission["archive"]["primary_entry"] == "b-big.md"
                    and len(case.estore.get_passages(source_id=primary))
                    >= len(case.estore.get_passages(source_id=other))
                ),
                "archive_claim_cites_verbatim": bool(report["attribution"]["claim"]["passage_ids"]),
                "archive_level_changed": report["status"] == "level_changed",
            },
            "detail": {
                "task_id": task_id,
                "archive": submission["archive"],
                "source_ids": submission["source_ids"],
                "primary": primary,
            },
        }
    finally:
        case.close()


def scenario_binding_missed(workdir: Path) -> dict:
    case = Scenario(workdir, "missed", second_capability=True)
    try:
        gap = case.scenario["gaps"]["practice"]
        task_id = create_active_task(case.store, gap)
        artifact = _artifact(case.workdir, "eval-set.md", "# 评测集\n\n10 条样本。\n")
        gateway = FakeGateway(
            responses={
                BINDING_TASK: make_binding_proposer(
                    path=case.scenario["other_capability_path"]
                )
            }
        )
        report = asyncio.run(case.loop(gateway).complete_task(task_id, artifact_path=artifact))
        return {
            "checks": {
                "missed_status_recorded": report["status"] == "binding_missed",
                "missed_no_assessment_written": report["assessment"] is None,
                "missed_task_done": case.store.get_task(task_id)["status"] == "done",
                "missed_levels_unchanged": (
                    case.store.get_capability(case.scenario["capability"])[
                        "current_level_practice"
                    ]
                    == 3
                ),
                "missed_trace_incomplete": (
                    report["attribution"]["guard"]["trace_complete"] is False
                ),
            },
            "detail": {
                "task_id": task_id,
                "binding": report["binding"]["reason"],
                "guard": report["attribution"]["guard"],
            },
        }
    finally:
        case.close()


def scenario_failure_retry(workdir: Path) -> dict:
    case = Scenario(workdir, "retry")
    try:
        gap = case.scenario["gaps"]["practice"]
        task_id = create_active_task(case.store, gap)
        artifact = _artifact(case.workdir, "eval-set.md", "# 评测集\n\n10 条样本。\n")

        broken = FakeGateway(fail_with={BINDING_TASK: RuntimeError("网关不可用（对例）")})
        failed = False
        try:
            asyncio.run(case.loop(broken).complete_task(task_id, artifact_path=artifact))
        except Exception as error:  # noqa: BLE001 - 冒烟如实记录失败类型
            failed = True
            failure_reason = f"{type(error).__name__}: {error}"
        active_after_failure = case.store.get_task(task_id)["status"] == "active"
        no_submission_after_failure = case.store.list_task_submissions(task_id=task_id) == []
        sources_before = len(case.estore.get_sources())

        report = asyncio.run(
            case.loop(case.fake_binding()).complete_task(task_id, artifact_path=artifact)
        )
        claims = [
            entry
            for entry in adapter.claims_overview(case.estore)
            if (entry["claim"].get("metadata") or {}).get("growth_task_id") == task_id
        ]
        return {
            "checks": {
                "retry_failure_is_fail_stop": failed,
                "retry_failure_leaves_active": active_after_failure and no_submission_after_failure,
                "retry_succeeds_idempotently": (
                    report["status"] == "level_changed"
                    and len(case.store.list_task_submissions(task_id=task_id)) == 1
                    and len(case.estore.get_sources()) == sources_before
                    and len(claims) == 1
                ),
            },
            "detail": {
                "task_id": task_id,
                "failure": failure_reason,
                "status_after_retry": report["status"],
            },
        }
    finally:
        case.close()


def scenario_guard_unit() -> dict:
    base = {
        "submission": {"source_id": "src_x"},
        "claim": {"claim_id": "clm_x"},
        "binding": {"bound_on_task_capability": True},
        "trace": {"complete": True},
        "before": {"practice": {"status": "rated", "level": 3}},
        "after": {"practice": {"status": "rated", "level": 4}},
        "level_changed_dimensions": ["practice"],
    }

    def raises(payload: dict) -> bool:
        try:
            verify_attribution(payload)
        except LoopGuardError:
            return True
        return False

    no_change = verify_attribution(
        {**base, "level_changed_dimensions": [], "trace": {"complete": False}}
    )
    return {
        "checks": {
            "guard_accepts_attributed_change": bool(verify_attribution(base)["trace_complete"]),
            "guard_rejects_missing_before": raises({**base, "before": {"practice": None}}),
            "guard_rejects_missing_provenance": raises({**base, "trace": {"complete": False}}),
            "guard_rejects_unbound_change": raises(
                {**base, "binding": {"bound_on_task_capability": False}}
            ),
            "guard_allows_no_change": no_change["trace_complete"] is False,
            "guard_rejects_level_drop": raises(
                {**base, "after": {"practice": {"status": "rated", "level": 2}}}
            ),
        },
        "detail": {},
    }


def scenario_boundaries(workdir: Path) -> dict:
    case = Scenario(workdir, "boundaries")
    try:
        gap = case.scenario["gaps"]["practice"]
        task_id = create_active_task(case.store, gap)
        artifact = _artifact(case.workdir, "eval-set.md", "# 评测集\n\n10 条样本。\n")
        asyncio.run(case.loop(case.fake_binding()).complete_task(task_id, artifact_path=artifact))
        tables = {
            row[0]
            for row in case.store.db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        events = case.store.list_events()
        return {
            "checks": {
                "boundaries_no_new_tables": {t for t in tables if t.startswith("g_")}
                == GOAL_EXPECTED_TABLES,
                "boundaries_frozen_event_kinds": {event["kind"] for event in events}
                == {"task_status_changed"},
                "boundaries_no_rating_contract_change": _rating_contract_version() == "m4c-1",
            },
            "detail": {
                "g_tables": sorted(t for t in tables if t.startswith("g_")),
                "event_kinds": sorted({event["kind"] for event in events}),
            },
        }
    finally:
        case.close()


def _rating_contract_version() -> str:
    from growth_os.assessment import RULES_CONTRACT_VERSION

    return RULES_CONTRACT_VERSION


# ---------------------------------------------------------------------------
# 真实运行
# ---------------------------------------------------------------------------


def scenario_real(workdir: Path) -> dict:
    from goal_flow_fixtures import HttpBudgetExceeded, HttpRequestBudget

    if os.getenv("M5_ALLOW_REAL_MODEL") != "1" and os.getenv("M4_ALLOW_REAL_MODEL") != "1":
        print("拒绝发起真实模型调用（未设 M5_ALLOW_REAL_MODEL=1 或 M4_ALLOW_REAL_MODEL=1）。")
        print(
            "命令：M5_ALLOW_REAL_MODEL=1 uv run --env-file .env "
            "python artifacts/m5c/run_task_loop.py --mode real"
        )
        raise SystemExit(2)

    os.environ["EVKG_HTTP_RETRIES"] = "1"  # 零额外重试
    case = Scenario(workdir, "real")
    budget = HttpRequestBudget(cap=1).install()
    try:
        gap = case.scenario["gaps"]["practice"]
        task_id = create_active_task(case.store, gap)
        artifact = SUBMISSION_DIR / "rag-eval-set.md"
        gateway = adapter.agent_gateway()
        failure = None
        report = None
        try:
            report = asyncio.run(
                case.loop(gateway).complete_task(task_id, artifact_path=artifact, note="M5-c 真实运行")
            )
        except HttpBudgetExceeded as error:  # pragma: no cover - fail-stop 记录
            failure = f"HttpBudgetExceeded: {error}"
        except Exception as error:  # noqa: BLE001 - 真实运行失败如实记录
            failure = f"{type(error).__name__}: {error}"
        finally:
            budget.uninstall()
        if report is None:
            return {
                "checks": {"real_run_completed": False},
                "detail": {"failure": failure, "requests": budget.requests},
            }
        attribution = report["attribution"]
        gaps = {
            item["id"]: item
            for item in case.store.list_gaps(capability_id=case.scenario["capability"])
        }
        metadata = adapter.source_metadata(case.estore, attribution["submission"]["source_id"])
        artifact_record = build_loop_artifact(report, mode="real", db_path=str(case.db))
        write_loop_artifact(HERE / "task-loop-real.json", artifact_record)
        return {
            "checks": {
                "real_run_completed": True,
                "real_run_within_budget": budget.requests == 1,
                "real_provider_recorded": bool(attribution["binding"]["provider"])
                and attribution["binding"]["provider"] != "fake",
                "real_status_level_changed": report["status"] == "level_changed",
                "real_practice_3_to_4": (
                    attribution["before"]["practice"]["level"] == 3
                    and attribution["after"]["practice"]["level"] == 4
                ),
                "real_gap_closed": gaps[gap["id"]]["status"] == "closed",
                "real_guard_all_true": all(attribution["guard"].values()),
                "real_trace_complete": trace_task(case.store, case.estore, task_id=task_id)[
                    "complete"
                ],
                "real_source_metadata_frozen": (
                    metadata["growth_evidence_type"] == "task_submission"
                    and metadata["growth_attribution"] == "user_declared"
                ),
                "real_report_written": bool(attribution["assessment"]["report_paths"]),
            },
            "detail": {
                "task_id": task_id,
                "requests": budget.requests,
                "provider": attribution["binding"]["provider"],
                "model": attribution["binding"]["model"],
                "before": attribution["before"],
                "after": attribution["after"],
                "closed_gap_ids": attribution["gaps"]["closed_gap_ids"],
                "claim_id": attribution["claim"]["claim_id"],
                "guard": attribution["guard"],
                "report_paths": attribution["assessment"]["report_paths"],
            },
        }
    finally:
        case.close()


def run(mode: str) -> dict:
    workdir = HERE / "tmp"
    workdir.mkdir(parents=True, exist_ok=True)
    checks: dict[str, bool] = {}
    detail: dict = {}
    try:
        if mode == "offline":
            for scenario in (
                scenario_happy,
                scenario_probe,
                scenario_archive,
                scenario_binding_missed,
                scenario_failure_retry,
                scenario_boundaries,
            ):
                outcome = scenario(workdir)
                checks.update(outcome["checks"])
                detail.update(outcome["detail"])
            guard = scenario_guard_unit()
            checks.update(guard["checks"])
        else:
            outcome = scenario_real(workdir)
            checks.update(outcome["checks"])
            detail.update(outcome["detail"])

        anchors = anchor_check()
        checks["real_db_untouched"] = anchors["content_hashes_match"] and anchors["counts_match"]
        checks["real_db_has_no_g_tables"] = anchors["g_tables_in_real_db"] == []
        detail["real_db_anchors"] = anchors
    except BaseException:
        gc.collect()
        raise

    result = {
        "mode": f"m5c-{mode}",
        "checks": checks,
        "checks_passed": sum(1 for value in checks.values() if value),
        "checks_total": len(checks),
        "all_checks_passed": all(checks.values()),
        "detail": detail,
    }
    (HERE / (f"result-{mode}.json" if mode == "real" else "result.json")).write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="M5-c 冒烟（offline / real）")
    parser.add_argument("--mode", choices=("offline", "real"), default="offline")
    args = parser.parse_args()
    result = run(args.mode)
    print(
        json.dumps(
            {
                "mode": result["mode"],
                "checks_passed": result["checks_passed"],
                "checks_total": result["checks_total"],
                "failed": [key for key, value in result["checks"].items() if not value],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if result["all_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
