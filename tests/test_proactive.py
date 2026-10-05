"""M7：主动事件、冷却、无变化不通知、用户关闭。"""

from datetime import UTC, datetime, timedelta
from pathlib import Path

from growth_os.proactive import ProactiveAnalyzer, ProactiveScheduler
from growth_os.store import GrowthStore


def build(store: GrowthStore, *, understanding: bool = False, done: bool = False, gap: bool = False) -> str:
    store.upsert_user("local", "本地用户")
    store.save_goal({"id": "goal_m7", "user_id": "local", "title": "目标", "direction": "AI", "purpose": "求职", "horizon": "六个月", "measurable_result": "完成项目", "status": "confirmed", "source_quote": "确认"})
    capability = store.upsert_capability({"goal_id": "goal_m7", "path": "RAG", "name": "RAG", "depth": 1, "target_level": 4})
    if understanding:
        store.save_assessment({"capability_id": capability, "dimension": "understanding", "status": "rated", "level": 2, "claim_ids": ["clm_u"], "rubric": {"contract": "m4c-1"}, "rationale": "理解证据"})
    if gap:
        store.db.execute("INSERT INTO g_gaps(id,user_id,goal_id,capability_id,dimension,current_level,target_level,severity,rationale,status) VALUES(?,?,?,?,?,?,?,?,?,?)", ("gap_p", "local", "goal_m7", capability, "practice", 1, 4, "level_gap_2plus", "差距大", "open"))
        store.db.commit()
    if done:
        store.db.execute("INSERT INTO g_gaps(id,user_id,goal_id,capability_id,dimension,current_level,target_level,severity,rationale,status) VALUES(?,?,?,?,?,?,?,?,?,?)", ("gap_d", "local", "goal_m7", capability, "practice", 3, 4, "level_gap_1", "差一级", "open"))
        store.db.commit()
        task = store.create_task({"gap_id": "gap_d", "title": "完成实践", "objective": "产出实践结果", "deliverable_type": "markdown", "est_minutes": 30, "acceptance_type": "artifact_check", "acceptance": "提交实践结果并核对内容"})
        store.activate_task(task)
        store.complete_task(task, source_id="src_done")
    return capability


def test_stall_notifies_once_and_respects_cooldown(tmp_path: Path):
    store = GrowthStore(str(tmp_path / "proactive.db"))
    try:
        build(store, understanding=True)
        now = datetime.now(UTC)
        first = ProactiveAnalyzer(store, now=now).run_daily()
        assert [item["kind"] for item in first["events"]] == ["practice_stalled"]
        assert len(first["notifications"]) == 1
        second = ProactiveAnalyzer(store, now=now + timedelta(days=1)).run_daily()
        assert second["events"] and second["notifications"] == []
    finally:
        store.close()


def test_no_change_and_disabled_do_not_notify(tmp_path: Path):
    store = GrowthStore(str(tmp_path / "quiet.db"))
    try:
        build(store, understanding=True, done=True)
        assert ProactiveAnalyzer(store).run_daily()["notifications"] == []
        build_gap = GrowthStore(str(tmp_path / "disabled.db"))
        build(build_gap, gap=True)
        build_gap.set_proactive_enabled(False)
        result = ProactiveAnalyzer(build_gap).run_daily()
        assert result["events"][0]["kind"] == "gap_without_task"
        assert result["notifications"] == []
        build_gap.close()
    finally:
        store.close()


class FrozenClock:
    def __init__(self, moment: datetime) -> None:
        self.moment = moment

    def now(self) -> datetime:
        return self.moment


def test_scheduler_is_idempotent_per_day_and_stops_on_error(tmp_path: Path):
    store = GrowthStore(str(tmp_path / "schedule.db"))
    try:
        build(store, understanding=True)
        moment = datetime.now(UTC)
        scheduler = ProactiveScheduler(store, clock=FrozenClock(moment))
        first = scheduler.trigger()
        second = scheduler.trigger()
        assert first["reused"] is False and second["reused"] is True
        assert first["run"]["analysis_date"] == second["run"]["analysis_date"]
        assert first["run"]["notification_ids"]
        assert first["run"]["goal_regeneration"] == "not_implemented"
        assert len(store.list_notifications()) == 1

        class BrokenAnalyzer(ProactiveAnalyzer):
            def run_daily(self) -> dict:
                raise RuntimeError("检测失败")

        next_day = moment.replace(day=moment.day + 1)
        original = ProactiveAnalyzer.run_daily
        ProactiveAnalyzer.run_daily = BrokenAnalyzer.run_daily
        try:
            try:
                ProactiveScheduler(store, clock=FrozenClock(next_day)).trigger()
            except RuntimeError:
                pass
            else:
                raise AssertionError("失败必须抛出")
        finally:
            ProactiveAnalyzer.run_daily = original
        assert any(event["kind"] == "proactive_run_failed" for event in store.list_events())
    finally:
        store.close()
        store.close()
