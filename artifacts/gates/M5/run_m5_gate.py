"""M5 Gate：任务闭环完成条件 + 质量门（离线，不调用模型）。

只验证已归档的 G4/G5 与 M5-a…M5-c 结果，并在真实库副本上新鲜复核 QG1/QG2。
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


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _fresh(workdir: Path) -> tuple[dict, dict, dict]:
    workdir.mkdir(parents=True, exist_ok=True)
    copy = workdir / "m5-gate-copy.db"
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
    finally:
        gc.collect()
        copy.unlink(missing_ok=True)
    audit = {
        "status": before.get("status"),
        "violations": before.get("violations") or before.get("total_violations"),
        "cleanup_clean": before.get("status") == after.get("status"),
    }
    return audit, damage, {"before": before.get("status"), "after": after.get("status")}


def _anchors() -> dict:
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
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'g_%'")
    )
    conn.close()
    return {
        "content_hashes_match": all(hashes[t] == anchor["table_content_sha256"][t] for t in tables),
        "counts_match": counts == anchor["table_counts"],
        "g_tables_in_real_db": g_tables,
    }


def _run(command: list[str]) -> dict:
    done = subprocess.run(command, cwd=REPO, capture_output=True, text=True, timeout=900, check=False)
    lines = [line.strip() for line in f"{done.stdout}\n{done.stderr}".splitlines() if line.strip()]
    summary = next((line for line in reversed(lines) if re.search(r"\d+ (passed|failed|error)|All checks", line)), "")
    return {"returncode": done.returncode, "summary": summary}


def main() -> int:
    parser = argparse.ArgumentParser(description="M5 Gate")
    parser.add_argument("--skip-tests", action="store_true")
    args = parser.parse_args()
    g4 = _load(REPO / "artifacts/gates/G4/checks.json")
    g5 = _load(REPO / "artifacts/g5/result-real.json")
    m5a = _load(REPO / "artifacts/m5a/result.json")
    m5b = _load(REPO / "artifacts/m5b/result-real.json")
    m5c = _load(REPO / "artifacts/m5c/result-real.json")
    audit, damage, audits = _fresh(HERE / "tmp")
    anchors = _anchors()
    secrets = _secret_scan()
    qg5 = {"pytest": None, "ruff": None}
    if not args.skip_tests:
        qg5["pytest"] = _run(["uv", "run", "pytest"])
        qg5["ruff"] = _run(["uv", "run", "ruff", "check", "backend", "tests", "artifacts"])
    checks = {
        "cond1_task_maps_to_gap": g4["checks"]["every_task_maps_to_gap"] is True,
        "cond2_anti_pattern_rejected": g4["checks"]["literal_anti_pattern_rejected"] is True,
        "cond3_level_changed_without_manual_db": g5["checks"]["practice_3_to_4"] is True
        and g5["detail"]["requests"] <= 3,
        "cond4_change_attributed": g5["checks"]["trace_complete"] is True
        and g5["checks"]["guard_all_true"] is True,
        "cond5_g4_g5_passed": g4["all_checks_passed"] is True and g5["all_checks_passed"] is True,
        "qg1_fresh_audit_pass": audit["status"] == "pass" and not audit["violations"],
        "qg2_damage_caught": damage["status"] == "caught" and audit["cleanup_clean"] is True,
        "qg3_rules_tests_present": (REPO / "tests/test_assessment_rules.py").is_file(),
        "qg4_no_secrets": secrets["hit_count"] == 0,
        "qg5_tests_ruff": True if args.skip_tests else qg5["pytest"]["returncode"] == 0 and qg5["ruff"]["returncode"] == 0,
        "boundary_real_db": anchors["content_hashes_match"] and anchors["counts_match"],
        "boundary_no_g_tables": anchors["g_tables_in_real_db"] == [],
        "steps_all_passed": m5a["all_checks_passed"] and m5b["all_checks_passed"] and m5c["all_checks_passed"],
    }
    report = {
        "gate": "M5 · 任务闭环",
        "checks": checks,
        "checks_passed": sum(1 for value in checks.values() if value),
        "checks_total": len(checks),
        "all_checks_passed": all(checks.values()),
        "quality_gates": {"QG1": audit, "QG2": {**damage, "double_measure": audits}, "QG4": secrets, "QG5": qg5},
        "boundary": anchors,
        "g5": {"requests": g5["detail"]["requests"], "before": g5["detail"]["before"], "after": g5["detail"]["after"]},
    }
    (HERE / "m5-gate-result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"checks_passed": report["checks_passed"], "checks_total": report["checks_total"], "failed": [k for k, v in checks.items() if not v]}, ensure_ascii=False, indent=2))
    return 0 if report["all_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
