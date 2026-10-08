"""确认操作的持久化与质量复核，不发真实模型请求。"""
import gc
import json
import os
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient
from growth_os.api.product import create_local_product_app
from verify_g6_final import ROOT, audit_copy, database_state, regression, secret_scan


def verify():
    output = ROOT / "artifacts/product"
    browser = json.loads((output / "browser-actions/browser-verification.json").read_text(encoding="utf-8"))
    live = json.loads((output / "actions-live/result.json").read_text(encoding="utf-8"))
    original = json.loads((output / "live/result.json").read_text(encoding="utf-8"))
    checks = {"browser_journey": browser["passed"], "browser_console_clean": browser["console_errors"] == [], "live_actions": live["passed"]}
    os.environ["GROWTH_PRODUCT_DIRECTORY"] = browser["directory"]
    os.environ["GROWTH_PRODUCT_DEMO"] = "1"
    with TestClient(create_local_product_app()) as client:
        parent = client.get(f"/api/onboarding/goals/{browser['goal_id']}").json()
        child = client.get(f"/api/onboarding/goals/{browser['revision_goal_id']}").json()
        actions = client.get(f"/api/product/goals/{browser['goal_id']}/actions").json()["actions"]
        adjustment = next(row for row in actions if row["kind"] == "capability_adjustment")
        node = next(row for row in parent["capabilities"] if row["id"] == adjustment["payload"]["capability_id"])
        checks["two_actions_reopened"] = len(actions) == 2
        checks["target_adjustment_reopened"] = node["target_level"] == 5 and node["origin"] == "adjusted"
        checks["no_grade_write"] = node["current_level_understanding"] is None and node["current_level_practice"] is None
        checks["revision_lineage_reopened"] = child["revision_of"]["goal_id"] == parent["goal"]["id"]
        checks["parent_confirmed_child_pending"] = parent["goal"]["status"] == "confirmed" and child["goal"]["status"] != "confirmed" and not child["capabilities"]
        tasks = client.get(f"/api/growth-loop/{browser['goal_id']}").json()["tasks"]
        checks["task_proposal_reopened"] = len(tasks) == 1 and tasks[0]["status"] == "proposed"
    with tempfile.TemporaryDirectory(prefix="action-final-", dir=ROOT / "tmp") as scratch:
        audit = audit_copy(Path(browser["directory"]) / "onboarding.db", Path(scratch) / "browser")
        checks["audit_pass"] = audit["before"]["status"] == "pass" and audit["after"]["status"] == "pass"
        checks["empty_browser_graph_skips_damage"] = audit["before"]["counts"]["passages"] == 0 and audit["damage"]["status"] == "skipped" and audit["data_restored_except_audit_log"]
        real_audit = audit_copy(Path(live["directory"]) / "onboarding.db", Path(scratch) / "real")
        checks["damage_caught_restored"] = real_audit["before"]["status"] == "pass" and real_audit["after"]["status"] == "pass" and real_audit["damage"]["status"] == "caught" and real_audit["data_restored_except_audit_log"]
        gc.collect()
    growth = regression("artifacts/product/actions-regression.xml")
    focused = regression("artifacts/product/actions-focused.xml")
    upstream = regression("artifacts/product/evkg-regression.xml")
    checks["growth_regression"] = growth["successful"]
    checks["focused_regression"] = focused["successful"]
    checks["upstream_regression"] = upstream["successful"]
    after = {relative: database_state(ROOT / relative) for relative in original["originals_before"]}
    checks["original_databases_unchanged"] = after == original["originals_before"]
    scan = secret_scan()
    checks["secret_scan_clean"] = scan["hit_count"] == 0 and scan["env_ignored_and_untracked"]
    report = {"passed": all(checks.values()), "checks": checks, "audit": audit, "real_audit": real_audit, "growth": growth, "focused": focused, "upstream": upstream, "secret_scan": scan}
    (output / "actions-result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "checks": len(checks), "failed": [key for key, value in checks.items() if not value]}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(verify())
