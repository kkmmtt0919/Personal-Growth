"""G6-c: fresh return/quality verification without model calls or user DB writes."""
from __future__ import annotations

import gc
import hashlib
import json
import re
import sqlite3
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from contextlib import closing
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts/gates/G6/g6c"
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "artifacts/gates/G6"))

from growth_os.evidence import adapter
from run_g6b import verify

TODAY = date(2026, 10, 5)
PATTERNS = (
    r"(?i)(api[_-]?key|token|secret)[ \t]*[:=][ \t]*[\"']?[A-Za-z0-9_\-]{20,}",
    r"\bsk-[A-Za-z0-9]{16,}",
    r"\bghp_[A-Za-z0-9]{20,}",
)
PLACEHOLDERS = ("your-", "your_", "xxx", "example", "placeholder", "change-me",
                "changeme", "redacted", "<")


def read(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def fingerprint(relative: str) -> dict:
    return {"path": relative, "sha256": hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()}


def regression(relative: str) -> dict:
    root = ET.parse(ROOT / relative).getroot()
    suites = list(root.iter("testsuite"))
    totals = {key: sum(int(suite.get(key, "0")) for suite in suites)
              for key in ("tests", "failures", "errors", "skipped")}
    return {**totals, "passed": totals["tests"] - totals["failures"] - totals["errors"]
            - totals["skipped"], "successful": bool(totals["tests"])
            and not any(totals[key] for key in ("failures", "errors", "skipped")),
            "cases": [f"{case.get('classname')}.{case.get('name')}"
                      for case in root.iter("testcase")], "evidence": fingerprint(relative)}


def database_state(database: Path) -> dict:
    with closing(sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True)) as connection:
        tables = sorted(row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ))
        hashes, counts = {}, {}
        for table in tables:
            quoted = '"' + table.replace('"', '""') + '"'
            rows = [json.dumps(list(row), ensure_ascii=False, sort_keys=True, default=str)
                    for row in connection.execute(f"SELECT * FROM {quoted}")]
            hashes[table] = hashlib.sha256("\n".join(sorted(rows)).encode()).hexdigest()
            counts[table] = len(rows)
    return {"table_hashes": hashes, "counts": counts}


def audit_copy(database: Path, scratch: Path) -> dict:
    copy = scratch / database.parent.name / "audit.db"
    copy.parent.mkdir(parents=True)
    source = sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True)
    destination = sqlite3.connect(str(copy))
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()
    original = database_state(copy)
    before = adapter.audit(copy)
    damage = adapter.damage_selftest(copy)
    after = adapter.audit(copy)
    cleaned = database_state(copy)
    restored = all(
        original["table_hashes"][table] == cleaned["table_hashes"].get(table)
        and original["counts"][table] == cleaned["counts"].get(table)
        for table in original["table_hashes"] if table != "audit_log"
    )
    return {"database": database.relative_to(ROOT).as_posix(), "before": before,
            "damage": damage, "after": after, "data_restored_except_audit_log": restored}


def secret_scan() -> dict:
    paths = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT).decode("utf-8").split("\0")
    hits, scanned = [], 0
    for relative in sorted(set(paths) - {""}):
        path = ROOT / relative
        if not path.is_file() or path.suffix.lower() in {
            ".db", ".png", ".jpg", ".zip", ".pyc", ".pdf", ".bundle"
        }:
            continue
        content = path.read_text(encoding="utf-8", errors="ignore")
        scanned += 1
        for pattern in PATTERNS:
            for match in re.finditer(pattern, content):
                if not any(marker in match.group().lower() for marker in PLACEHOLDERS):
                    # Never retain or print matched credentials.
                    hits.append({"file": relative, "line": content[:match.start()].count("\n") + 1})
    ignored = subprocess.run(
        ["git", "check-ignore", "--quiet", ".env"], cwd=ROOT, check=False).returncode == 0
    tracked = bool(subprocess.check_output(["git", "ls-files", "--", ".env"], cwd=ROOT).strip())
    return {"scanned_files": scanned, "hit_count": len(hits), "locations": hits,
            "env_ignored_and_untracked": ignored and not tracked}


def archived_gates() -> dict:
    session = read("artifacts/m2/session-real.json")
    trace = read("artifacts/gates/G2/traceability.json")
    audit = read("artifacts/gates/G2/audit.json")
    comparison = read("artifacts/gates/G3/comparison.json")
    g4 = read("artifacts/gates/G4/checks.json")
    g5 = read("artifacts/gates/G5/checks.json")
    goal = session["goal"]
    passed = {
        "G1": session["mode"] == "real" and session["all_checks_passed"]
        and 1 <= len(session["clarification"]["rounds"]) <= 6 and goal["status"] == "confirmed"
        and all(goal[key] for key in ("direction", "purpose", "horizon", "measurable_result")),
        "G2": trace["sample_count"] >= 5 and trace["all_traceable_complete"]
        and audit["status"] == "pass" and audit["total_violations"] == 0,
        "G3": comparison["passed"] and read("artifacts/gates/M4/m4-gate-result.json")["all_checks_passed"],
        "G4": g4["all_checks_passed"] and all(g4["checks"].values()),
        "G5": g5["all_checks_passed"] and all(g5["checks"].values()) and g5["requests"] > 0,
    }
    records = {
        "G1": ("2026-10-02", ["artifacts/m2/session-real.json", "artifacts/gates/G1/session-replay.png"],
               "真实模型历史会话；截图为历史回放，未实现实时目标澄清 UI。"),
        "G2": ("2026-10-03", ["artifacts/gates/G2/traceability.json", "artifacts/gates/G2/audit.json"],
               "执行基线采用全量七条追溯、确定性抽五条；不宣称随机抽样。"),
        "G3": ("2026-10-03", ["artifacts/gates/G3/comparison.json"],
               "冻结基线为 RAG 材料与 NULL/不足语义；不冒充原 PRD Memory 示例。"),
        "G4": ("2026-10-03", ["artifacts/gates/G4/checks.json"],
               "两条任务接受、四条反例拒绝；不由质量规则宣称学习收益。"),
        "G5": ("2026-10-04", ["artifacts/gates/G5/checks.json", "artifacts/gates/M5/m5-gate-result.json"],
               "真实模型历史闭环；本轮离线回归，不重新调用模型或续期历史实验。"),
    }
    return {
        gate: {"recorded_pass": bool(passed[gate]), "evidence_date": recorded,
               "within_90_days": 0 <= (TODAY - date.fromisoformat(recorded)).days <= 90,
               "historical_model_run_reexecuted": False, "note": note,
               "artifacts": [fingerprint(item) for item in files]}
        for gate, (recorded, files, note) in records.items()
    }


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    databases = [ROOT / "data/growth.db", ROOT / "data/demo-return/demo.db"]
    originals = {str(database): database_state(database) for database in databases}
    persistent = verify(ROOT / "data/demo-return")
    with tempfile.TemporaryDirectory(prefix="g6c-audit-", dir=ROOT / "tmp") as directory:
        audits = [audit_copy(database, Path(directory)) for database in databases]
        gc.collect()
    unchanged = all(originals[str(database)] == database_state(database) for database in databases)
    growth = regression("artifacts/gates/G6/g6c/growth-regression.xml")
    upstream = regression("artifacts/gates/G6/g6c/evkg-regression.xml")
    rules = [case for case in growth["cases"] if "test_assessment_rules." in case]
    returns = [case for case in growth["cases"] if "test_return_summary." in case]
    frontend = read("artifacts/frontend-redesign/verification.json")
    engineering = read("artifacts/gates/G6/g6c/validation.json")
    gates = archived_gates()
    secrets = secret_scan()
    quality = {
        "QG1": all(item["before"]["status"] == item["after"]["status"] == "pass"
                   and item["before"]["total_violations"] == item["after"]["total_violations"] == 0
                   for item in audits),
        "QG2": all(item["damage"]["status"] == "caught" and item["data_restored_except_audit_log"]
                   for item in audits),
        "QG3": growth["successful"] and bool(rules),
        "QG4": secrets["hit_count"] == 0 and secrets["env_ignored_and_untracked"],
        "QG5": growth["successful"] and upstream["successful"],
    }
    source_paths = [
        "backend/growth_os/agent/return_summary.py", "backend/growth_os/store/growth_store.py",
        "backend/growth_os/api/local.py", "backend/growth_os/api/app.py",
        "frontend/src/components/ReturnSummary.tsx", "frontend/src/pages/Dashboard.tsx",
        "frontend/src/components/CapabilityMap.tsx", "frontend/src/index.css",
        "scripts/verify_g6_final.py", "scripts/verify_frontend_redesign.cjs",
    ]
    fresh_visuals = [
        "artifacts/frontend-redesign/dashboard-1440.png",
        "artifacts/frontend-redesign/dashboard-390.png",
        "artifacts/frontend-redesign/verification.json",
        "artifacts/gates/G6/screenshots/return-sources.png",
    ]
    checks = {
        "persistent_return_all_ten_checks": persistent["all_checks_passed"],
        "return_counterexamples_current_regression": growth["successful"] and len(returns) >= 20,
        "current_frontend_53_checks": len(frontend["checks"]) >= 53
        and all(check["passed"] for check in frontend["checks"]) and not frontend["browserErrors"],
        "historical_g1_g5_records_valid_under_frozen_baselines": all(
            gate["recorded_pass"] and gate["within_90_days"] for gate in gates.values()),
        "fresh_qg1_qg5": all(quality.values()),
        "current_build_lint_ruff": all(engineering[key]["exit_code"] == 0
                                       for key in ("backend_ruff", "frontend_build", "frontend_lint")),
        "original_databases_unchanged": unchanged,
    }
    result = {
        "stage": "G6-c", "date": TODAY.isoformat(), "model_requests_this_verification": 0,
        "g6_passed": all(checks.values()), "frozen_scope_verified": all(checks.values()),
        "full_prd_mvp_accepted": False, "checks": checks, "quality_gates": quality,
        "historical_gates": gates, "persistent_return": persistent, "fresh_audits": audits,
        "secret_scan": secrets, "growth_regression": growth, "upstream_regression": upstream,
        "rating_rule_cases": len(rules), "return_counterexample_cases": len(returns),
        "frontend_verification": fingerprint("artifacts/frontend-redesign/verification.json"),
        "engineering_verification": fingerprint("artifacts/gates/G6/g6c/validation.json"),
        "visual_evidence": [fingerprint(item) for item in fresh_visuals],
        "current_sources": [fingerprint(item) for item in source_paths],
        "remaining_scope": ["实时目标澄清 UI", "上传写入口与产品 PDF 页码定位",
                            "OAuth/私有仓库", "Evidence 攻击详情", "Mentor Chat",
                            "外部通知/自动重建", "发布前依赖归档刷新与 commit pin",
                            "独立验收证据库自举"],
        "limitations": ["确定性只读返回输出；受控材料、偏好与次日时钟。",
                        "本轮没有真实模型导师推理验证或对外发布。",
                        "历史 G1–G5 与当前回归分开记录；历史实验未续期。",
                        "来源展开旧截图保留为历史证据；当前样式使用改版截图和交互检查。"],
    }
    (OUTPUT / "result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"g6_passed": result["g6_passed"], "checks": checks,
                      "quality_gates": quality, "growth_tests": growth["passed"],
                      "upstream_tests": upstream["passed"], "secret_hits": secrets["hit_count"]},
                     ensure_ascii=False))
    return 0 if result["g6_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
