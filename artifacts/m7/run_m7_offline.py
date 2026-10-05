"""M7-c：离线复核主动分析的前四项，并明确第五项未实现。"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "backend"))
sys.path.insert(0, str(REPO / "tests"))

from growth_os.proactive import ProactiveAnalyzer, ProactiveScheduler
from growth_os.store import GrowthStore
from test_proactive import FrozenClock, build


def main() -> int:
    work = HERE / "tmp"
    work.mkdir(exist_ok=True)
    checks = {}
    now = datetime.now(UTC)

    stall = GrowthStore(str(work / "stall.db"))
    build(stall, understanding=True)
    stalled = ProactiveScheduler(stall, clock=FrozenClock(now)).trigger()
    checks["practice_stall_notifies"] = stalled["run"]["event_kinds"] == ["practice_stalled"] and bool(stalled["run"]["notification_ids"])
    stall.close()

    quiet = GrowthStore(str(work / "quiet.db"))
    build(quiet, understanding=True, done=True)
    checks["no_change_no_notification"] = ProactiveAnalyzer(quiet, now=now).run_daily()["notifications"] == []
    quiet.close()

    cooldown = GrowthStore(str(work / "cooldown.db"))
    build(cooldown, understanding=True)
    ProactiveAnalyzer(cooldown, now=now).run_daily()
    checks["cooldown_suppresses_repeat"] = ProactiveAnalyzer(cooldown, now=now + timedelta(days=1)).run_daily()["notifications"] == []
    cooldown.close()

    disabled = GrowthStore(str(work / "disabled.db"))
    build(disabled, gap=True)
    disabled.set_proactive_enabled(False)
    disabled_result = ProactiveAnalyzer(disabled, now=now).run_daily()
    checks["disabled_detects_without_notification"] = bool(disabled_result["events"]) and disabled_result["notifications"] == []
    disabled.close()

    checks["goal_regeneration_not_implemented"] = stalled["run"]["goal_regeneration"] == "not_implemented"
    result = {"checks": checks, "checks_passed": sum(checks.values()), "checks_total": len(checks), "all_checks_passed": all(checks.values())}
    (HERE / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["all_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
