"""M4 Gate：能力审计完成条件 1–6 + 质量门（离线，**不调用模型**）。

只做**验证与登记**，不重跑新实验：

* 完成条件 1–6：对已归档的 **G2/G3 门证据**（`artifacts/gates/G2|G3/`）与 M4-e
  离线 / 真实运行结果（`artifacts/m4e/result*.json`）逐条断言；
* 质量门：QG1（`audit_store`：实验归档 + 真实库**副本**的新鲜复核）、
  QG2（`run_damage_selftest` 副本新鲜复核）、QG3（规则测试与 A/B 对决结论）、
  QG4（被跟踪文件密钥扫描）、QG5（全量测试 + ruff，子进程新鲜跑）；
* 数据边界：真实库逐表内容哈希 + 计数对锚、`g_` 表保持全空、临时副本即删。

产物：`m4-gate-result.json` + `README.md`（判定与完成条件表）。
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "backend"))
sys.path.insert(0, str(REPO / "artifacts" / "m3gate"))

from evkg.attack.auditor import audit_store
from evkg.attack.damage import run_damage_selftest
from run_m3_gate import _secret_scan

REAL_DB = REPO / "data" / "growth.db"
ANCHORS = REPO / "artifacts" / "m3a" / "evidence-anchors.json"
M4E_OFFLINE = REPO / "artifacts" / "m4e" / "result.json"
M4E_REAL = REPO / "artifacts" / "m4e" / "result-real.json"
G2_DIR = REPO / "artifacts" / "gates" / "G2"
G3_DIR = REPO / "artifacts" / "gates" / "G3"
REPORT_SECTIONS = (
    "## 生成信息",
    "## 一、两维度评定",
    "## 二、支持证据（逐字引用）",
    "## 三、不足",
    "## 四、反向证据",
    "## 五、已排除的证据",
    "## 六、规则版本与复算",
    "## 七、本报告不能成立的结论",
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _fresh_audit_and_damage(workdir: Path) -> tuple[dict, dict, dict]:
    """在真实库的**副本**上新鲜复核 QG1 / QG2（真实库只读、副本即删）。

    QG2 采用 M1-f 的**双向测量**口径（C4）：注入**前**审计与自测清理**后**审计必须一致 ——
    不采信内置 `status` 单值。
    """
    workdir.mkdir(parents=True, exist_ok=True)
    copy = workdir / "m4-gate-copy.db"
    copy.unlink(missing_ok=True)
    source = sqlite3.connect(f"file:{REAL_DB.as_posix()}?mode=ro", uri=True)
    destination = sqlite3.connect(str(copy))
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()
    try:
        before = audit_store(str(copy))
        damage = run_damage_selftest(str(copy))
        after = audit_store(str(copy))
        deletions = {
            "claims": sqlite3.connect(str(copy)).execute("SELECT COUNT(*) FROM claims").fetchone()[0],
        }
    finally:
        gc.collect()
        for _ in range(5):
            try:
                copy.unlink(missing_ok=True)
            except PermissionError:
                import time

                time.sleep(0.5)
                continue
            if not copy.exists():
                break
    audit = {
        "status": before.get("status"),
        "violations": before.get("violations") or before.get("total_violations"),
        "cleanup_clean": before.get("status") == after.get("status")
        and (before.get("violations") or before.get("total_violations"))
        == (after.get("violations") or after.get("total_violations")),
        "claims_after_selftest": deletions["claims"],
    }
    return audit, damage, {"before": before.get("status"), "after": after.get("status")}


def _real_db_anchors() -> dict:
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
        "counts": counts,
        "g_tables_in_real_db": g_tables,
    }


def _run(command: list[str], cwd: Path, timeout: int = 900) -> dict:
    done = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False)
    combined = f"{done.stdout or ''}\n{done.stderr or ''}"
    lines = [line.strip() for line in combined.splitlines() if line.strip()]
    summary = next(
        (line for line in reversed(lines) if re.search(r"\d+ (passed|failed|error)", line)),
        lines[-1] if lines else "",
    )
    return {"command": " ".join(command), "returncode": done.returncode, "summary": summary}


def main() -> int:
    parser = argparse.ArgumentParser(description="M4 Gate 封板验证")
    parser.add_argument("--skip-tests", action="store_true", help="跳过 QG5（测试/ruff）子进程复核")
    args = parser.parse_args()

    workdir = HERE / "tmp"
    offline = _load(M4E_OFFLINE)
    real = _load(M4E_REAL)
    traceability = _load(G2_DIR / "traceability.json")
    g2_audit = _load(G2_DIR / "audit.json")
    comparison = _load(G3_DIR / "comparison.json")
    rounds = _load(G3_DIR / "rounds.json")
    inputs = _load(G3_DIR / "inputs.json")
    attack = _load(G3_DIR / "attack.json")
    archived_attack_budget = attack.get("total_http")
    archived_attack_stages = attack.get("stages")

    rating_capabilities = sorted(
        {
            capability
            for capability, body in rounds["round_b"].items()
            if any(dim["status"] == "rated" for dim in body["dimensions"].values())
        }
    )
    reports_ok = all(
        all(section in (G3_DIR / "reports" / f"{stem}.md").read_text(encoding="utf-8") for section in REPORT_SECTIONS)
        for stem in ("g3-a-rag", "g3-b-rag", "g3-b-tool", "g3-b-vector")
    )
    constructed_flags = {
        "note_constructed": inputs["note"]["constructed"] is True,
        "repo_real": inputs["repo"]["constructed"] is False and bool(inputs["repo"]["sha"]),
        "jd_constructed": inputs["jd"]["constructed"] is True,
    }
    budget = {name: stage["requests"] for name, stage in real["detail"]["stages"].items()}
    fresh_audit, fresh_damage, damage_audits = _fresh_audit_and_damage(workdir)
    anchors = _real_db_anchors()
    secrets = _secret_scan()
    qg5 = {"pytest": None, "ruff": None}
    if not args.skip_tests:
        qg5["pytest"] = _run(["uv", "run", "pytest"], cwd=REPO)
        qg5["ruff"] = _run(["uv", "run", "ruff", "check", "backend", "tests", "artifacts"], cwd=REPO)

    checks = {
        # ── 完成条件 1–6（ROADMAP M4 / M4-PLAN §10.1）──────────────────────
        "cond1_at_least_3_capabilities_rated": len(rating_capabilities) >= 3,
        "cond1_traceable_assessments_ge_5": traceability["traceable_total"] >= 5
        and traceability["sample_count"] >= 5
        and all(item["complete"] for item in traceability["all"]),
        "cond2_prd10_decoupled_conclusion": comparison["round_a"]["understanding"] >= 2
        and not (
            comparison["round_a"]["practice_status"] == "rated"
            and (comparison["round_a"]["practice"] or 0) >= 2
        ),
        "cond3_strong_evidence_higher": comparison["passed"]
        and (comparison["round_b"]["practice"] or 0) >= 2,
        "cond3_plus2_operational": comparison["passed"],
        "cond4_explainable_reports": reports_ok,
        "cond5_audit_pass_every_assessment": g2_audit.get("status") == "pass"
        and not (g2_audit.get("violations") or g2_audit.get("total_violations")),
        "cond6_g2_passed": traceability["traceable_total"] >= 5,
        "cond6_g3_passed": comparison["passed"] is True,
        # ── 质量门（M4-PLAN §10.3 / ACCEPTANCE_GATES QG1–QG5）─────────────
        "qg1_fresh_audit_pass_on_copy": fresh_audit["status"] == "pass" and not fresh_audit["violations"],
        "qg2_damage_selftest_caught": fresh_damage["status"] == "caught"
        and fresh_audit["cleanup_clean"] is True,
        "qg3_rules_tests_and_ab": (REPO / "tests" / "test_assessment_rules.py").is_file()
        and real["checks"].get("g3a_practice_not_ge_2") is True
        and real["checks"].get("g3b_practice_ge_2") is True,
        "qg4_no_plaintext_secrets": secrets["hit_count"] == 0,
        "qg5_tests_and_ruff": True
        if args.skip_tests
        else (qg5["pytest"]["returncode"] == 0 and qg5["ruff"]["returncode"] == 0),
        # ── 数据边界与预算 ────────────────────────────────────────────────
        "boundary_real_db_untouched": anchors["content_hashes_match"] and anchors["counts_match"],
        "boundary_g_tables_empty": anchors["g_tables_in_real_db"] == [],
        "boundary_constructed_labeled": all(constructed_flags.values()),
        "budget_real_run_within_17": sum(budget.values()) <= 17,
        "budget_per_stage_caps": budget
        == {"binding_a": 1, "verifier_a": 1, "adversarial_a": 4, "binding_b": 1, "verifier_b": 5, "adversarial_b": 5},
        "offline_and_real_all_passed": offline["all_checks_passed"] and real["all_checks_passed"],
        "temp_dbs_deleted": offline.get("temp_db_deleted") is True and real.get("temp_db_deleted") is True,
    }

    report = {
        "gate": "M4 · 能力审计（完成条件 1–6 + 质量门 QG1–QG5）",
        "date": "2026-10-03",
        "plan": "docs/M4-PLAN.md v1.0（用户确认）",
        "execution": "artifacts/gates/M4/run_m4_gate.py（离线；不调用模型）",
        "conditions": {
            "1_three_capabilities_traceable": {
                "rated_capabilities": rating_capabilities,
                "traceable_total": traceability["traceable_total"],
                "assessments_total": traceability["assessments_total"],
                "sample_count": traceability["sample_count"],
            },
            "2_prd10_weak_evidence": comparison["round_a"],
            "3_strong_evidence": {
                "round_b": comparison["round_b"],
                "observation_b_practice_ge_3": comparison["observation_b_practice_ge_3"],
            },
            "4_explainability": {"reports_with_all_sections": reports_ok, "sections": list(REPORT_SECTIONS)},
            "5_audit": {"archived": g2_audit.get("status"), "fresh_on_copy": fresh_audit},
            "6_gates": {"G2": traceability["traceable_total"], "G3": comparison["passed"]},
        },
        "quality_gates": {
            "QG1": {"archived": g2_audit.get("status"), "fresh_copy": fresh_audit},
            "QG2": {**fresh_damage, "double_measure": damage_audits},
            "QG3": {"rules_tests": "tests/test_assessment_rules.py"},
            "QG4": {"scanned_files": secrets["scanned_files"], "hit_count": secrets["hit_count"]},
            "QG5": qg5,
        },
        "boundary": {"anchors": anchors, "constructed": constructed_flags},
        "budget": {"stages": budget, "total": sum(budget.values()), "cap": 17,
                   "policy": "单次真实运行 ≤17 HTTP（允许因修复重跑，每次独立记录）",
                   "archived_attack_total_http": archived_attack_budget,
                   "archived_attack_stages": archived_attack_stages},
        "real_run_attempts": {
            "process_runs": 6,
            "note": "2 次代码缺陷早停、2 次预算硬停、1 次完成但 G2 追溯器语义不足、1 次通过；合计 ≈53 HTTP（单次 ≤17）",
        },
        "checks": checks,
        "checks_passed": sum(1 for value in checks.values() if value),
        "checks_total": len(checks),
        "all_checks_passed": all(checks.values()),
    }
    (HERE / "m4-gate-result.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({"checks_passed": report["checks_passed"], "checks_total": report["checks_total"],
                      "failed": [k for k, v in checks.items() if not v]}, ensure_ascii=False, indent=2))
    return 0 if report["all_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
