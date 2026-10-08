"""U1最终复核：复用已完成旅程，离线核对持久化、原库和副本审计。"""
import json
import sqlite3
import tempfile
from pathlib import Path

from verify_g6_final import ROOT, audit_copy, database_state, regression, secret_scan


def verify():
    output = ROOT / "artifacts/product"
    live = json.loads((output / "live/result.json").read_text(encoding="utf-8"))
    offline = json.loads((output / "browser-offline/browser-verification.json").read_text(encoding="utf-8"))
    browser = json.loads((output / "browser-live/browser-verification.json").read_text(encoding="utf-8"))
    startup = json.loads((output / "startup-smoke.json").read_text(encoding="utf-8"))
    checks = {"live_journey": live["passed"], "offline_browser": offline["passed"],
              "live_browser": browser["passed"], "startup_smoke": startup["passed"]}
    actual = {relative: database_state(ROOT / relative) for relative in live["originals_before"]}
    checks["original_databases_unchanged"] = actual == live["originals_before"]
    database = Path(live["directory"]) / "onboarding.db"
    with sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True) as connection:
        rows = connection.execute("SELECT status,response,context FROM g_mentor_turns WHERE goal_id=? ORDER BY rowid", (live["goal"]["id"],)).fetchall()
        checks["persisted_three_replies"] = len(rows) == 3 and all(row[0] == "completed" for row in rows)
        checks["actual_model_no_fake"] = all(json.loads(row[1])["provider"] != "fake" for row in rows)
        context = json.loads(rows[-1][2])
        checks["mentor_reads_goal_memory_capability_evidence_history"] = all(context[key] for key in ("goal", "memory", "capabilities", "evidence", "growth_history"))
        runs = connection.execute("SELECT provider FROM g_agent_runs").fetchall()
        checks["seven_bounded_model_runs"] = len(runs) == 7 and all(row[0] != "fake" for row in runs)
    with tempfile.TemporaryDirectory(prefix="product-audit-", dir=ROOT / "tmp") as scratch:
        audit = audit_copy(database, Path(scratch))
        checks["audit_pass"] = audit["before"]["status"] == "pass" and audit["after"]["status"] == "pass"
        checks["copy_damage_caught_restored"] = audit["damage"]["status"] == "caught" and audit["data_restored_except_audit_log"]
    growth = regression("artifacts/product/regression.xml")
    upstream = regression("artifacts/product/evkg-regression.xml")
    checks["growth_regression"] = growth["successful"]
    checks["upstream_regression"] = upstream["successful"]
    scan = secret_scan()
    checks["secret_scan_clean"] = scan["hit_count"] == 0 and scan["env_ignored_and_untracked"]
    result = {"passed": all(checks.values()), "checks": checks, "model_calls": len(runs),
              "growth": growth, "upstream": upstream, "audit": audit, "secret_scan": scan,
              "originals_after": actual, "offline_browser_checks": len(offline["checks"]),
              "live_browser_checks": len(browser["checks"])}
    (output / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"passed": result["passed"], "checks": len(checks), "model_calls": len(runs), "failed": [key for key, value in checks.items() if not value]}))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(verify())
