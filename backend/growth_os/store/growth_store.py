"""Growth OS 自有的 `g_` 表族存储（L2）。

边界（由 `tests/test_adapter_boundary.py` 的可执行检查守着）：

* 本模块**只碰 `g_` 前缀的表**，不 import evkg、不读写证据表族；
* 与 evkg 表族同库共存（决定 D2），跨表族引用（`claim_id` / `source_id`）
  由应用层保证 —— M2 不产生这类引用。

    M2 的三条数据语义（来自 `M2-PLAN.md` §3.1，均为验收项）：

1. **稳定逻辑标识**：能力点 id 由 `goal_id + path + name` 决定，与生成批次、模型、
   时间无关。再生成走 upsert，不得重复累积 —— 这是 M1-b.5c「id 含内容导致静默累积」
   教训在能力树上的对应物。
2. **人工调整受保护**：`origin=adjusted` 的行在再生成时保留 `target_level` 与
   `adjustment_note`（补充约束 C1）。
3. **未评估 ≠ 低等级**：M2 阶段 `current_level` 恒为 NULL，`current_level_status`
   恒为 `unassessed`；写入非空 `current_level` 会直接报错，而不是被静默接受
   （沿用 M1-b.5b「缺失不得伪装成数字」的语义）。M4-d 起允许回填维度化等级列
   （`current_level_understanding` / `current_level_practice`），但只能经
   `apply_assessment_levels` 显式方法，不允许 upsert/adjust 直接写。
4. **M4-a 的生命周期与草案语义**：能力节点带 `generation_id` / `status`
   （history + current view，§4）；assessment 只允许草案状态且 `level` 恒为 NULL ——
   星级算法不在本步，写入任何等级数字都报错。

M4-d 的维度化等级列（用户 2026-10-03 冻结）：

- **`current_level`**（legacy，标注 deprecated）：保留列、停用不写；新代码禁止读写。
- **`current_level_understanding` / `current_level_practice`**（维度化）：
  可存储理解与实践两个独立等级（1..5 或 NULL）；只能由 `apply_assessment_levels`
  显式回填（从 `g_assessments` 的 latest_assessment 取值），不得通过
  upsert/adjust/generate 路径直接写入 —— 违反即报错。
- **`current_level_status`**：扩为 `unassessed` / `assessed` 两态；
  两个维度均为 NULL → `unassessed`；至少一个维度非 NULL → `assessed`。
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
from pathlib import Path
from typing import Any, Self

GOAL_STATUSES = ("draft", "clarifying", "proposed", "confirmed", "archived")
CAPABILITY_ORIGINS = ("generated", "adjusted")
VERIFICATION_STATUSES = ("unverified", "verified")
RUN_STATUSES = ("ok", "error")
MODEL_SOURCES = ("result", "config_on_error")
TARGET_LEVEL_RANGE = (1, 5)

CAPABILITY_STATUSES = ("active", "superseded", "archived")
"""能力节点生命周期（M4-PLAN v1.0 §4，history + current view）。

再生成不删除历史：旧批次中不在新树的 `generated` 节点 → `superseded`；
`adjusted` 节点不自动降级；当前视图 = `active`。
"""

ASSESSMENT_STATUSES = ("draft", "insufficient_evidence", "rated")
"""assessment 状态：M4-a/b 只产出草案（`draft` / 证据不足）；M4-c 起允许 `rated`。"""

DRAFT_STATUSES = ("draft", "insufficient_evidence")
"""草案阶段的状态（`level` 恒 NULL）；M4-c 的评定写入走 `save_assessment`。"""

CAPABILITY_LEVEL_STATUSES = ("unassessed", "assessed")
"""能力点评估状态（M4-d 扩展）：
- unassessed: 两个维度均无有效评级（或能力点从未被评估）
- assessed: 至少存在一个维度有有效评级
"""

ASSESSMENT_DIMENSIONS = ("understanding", "practice")
"""两个独立维度（用户 2026-10-03 冻结）：理解与实践不合并成单一等级。"""

LEVEL_RANGE = (1, 5)
"""星级取值范围（PRD §9.1 五级）。"""

CLAIM_ROLES = ("supports", "gap")
"""`g_capability_claims` 桥表角色（ARCHITECTURE §4.3）。"""

GAP_SEVERITIES = ("evidence_gap", "level_gap_1", "level_gap_2plus")
"""缺口严重度（M4-e 冻结）：只表达「与目标的差 + rubric 缺口」，不承担能力诊断。

- `evidence_gap`：评定为 `insufficient_evidence` —— 缺可核验证据，**不判定为低能力**；
- `level_gap_1` / `level_gap_2plus`：已评定但低于目标（差 1 / 差 ≥2 级）。
"""

GAP_STATUSES = ("open", "closed")
"""缺口状态：M4-e 只产生 `open`；重算后不再成立 → `closed`（保留行，不删除历史）。"""

TASK_STATUSES = ("proposed", "active", "blocked", "done", "abandoned")
"""任务状态（M5-PLAN v1.0 §5，用户冻结）。

`done` 是**终态**且唯一入口 = `complete_task`（提交即完成）；非法转移直接报错。
"""

TASK_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "proposed": ("active", "abandoned"),
    "active": ("blocked", "abandoned", "done"),
    "blocked": ("active", "abandoned"),
    "done": (),
    "abandoned": (),
}
"""合法状态转移表（写死；非法转移报错，不静默兜底）。"""

TASK_DELIVERABLE_TYPES = ("markdown", "code", "archive", "probe_answer")
"""交付物类型（用户冻结四枚举）。**决定入库证据类型**（不由 LLM 决定）。"""

DIMENSION_DELIVERABLE_TYPES: dict[str, tuple[str, ...]] = {
    "understanding": ("probe_answer",),
    "practice": ("markdown", "code", "archive"),
}
"""维度 ↔ 交付物（用户冻结）：理解缺口只允许 `probe_answer`（probe_result 才能升理解）；
实践缺口只允许产出型交付物。"""

DELIVERABLE_EVIDENCE_TYPE: dict[str, str] = {
    "markdown": "task_submission",
    "code": "task_submission",
    "archive": "task_submission",
    "probe_answer": "probe_result",
}
"""交付物 → 证据类型（用户冻结映射）：markdown/code/archive → `task_submission`（实践 4）；
`probe_answer` → `probe_result`（理解 2→3）。**不因"看起来像笔记"降级为 uploaded_doc。**"""

TASK_ACCEPTANCE_TYPES = ("artifact_check", "test_run", "probe_rubric")
"""验收方式三枚举（用户冻结）。"""

TASK_EST_MINUTES_RANGE = (10, 600)
"""预计时长区间（分钟）：只做区间校验，不评准确性（M5 无 UI 计时）。"""

TASK_ACCEPTANCE_ANTI_PATTERNS = ("去学习", "学习一下", "了解一下", "熟悉一下", "复习一下", "随便看看")
"""不可验收表述（PRD §12）：任务不是学习提醒 —— 契约层挡"显然不可验收"的输入，
更细的可验收性判定与"改造"在 M5-b 生成器闸门里做。"""

TASK_EVENT_KINDS = ("task_status_changed",)
"""M5 冻结的 `g_events.kind`（M7 起追加自己的 kind，不复用本表语义做别的事）。"""

GOAL_ELEMENTS = ("direction", "purpose", "horizon", "measurable_result")
"""confirmed goal 必须齐全的四要素：方向 / 目的 / 时间周期 / 可衡量结果。"""


def default_db_path() -> str:
    """`GROWTH_DB` 未设置时与证据库同文件（D2：单 SQLite，双表族）。"""
    return os.getenv("GROWTH_DB", "data/growth.db")


def normalize_name(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip().casefold()


def gap_id(capability_id_: str, dimension: str) -> str:
    """缺口的稳定逻辑标识：一个（能力点 × 维度）最多一条当前缺口（幂等重算）。"""
    return f"gap_{capability_id_}_{dimension}"


def task_id(gap_id_: str, deliverable_type: str, run_id: str, seq: int) -> str:
    """任务的稳定逻辑标识：由「缺口 + 交付物类型 + 生成运行 + 序号」派生。

    与能力点不同，**任务可以累积**（同一缺口在不同时间会有多个任务）—— 因此 id 含生成批次
    与序号：同一次生成幂等，跨生成是新任务。
    """
    seed = f"{gap_id_}|{deliverable_type}|{run_id}|{seq}"
    return "task_" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:20]


def submission_id(task_id_: str, source_id: str) -> str:
    """提交记录的稳定逻辑标识：同一（任务 × 来源）重复提交命中同一行（幂等）。"""
    seed = f"{task_id_}|{source_id}"
    return "sub_" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def capability_id(goal_id: str, path: str, name: str) -> str:
    """能力点的稳定逻辑标识（与内容/批次无关）。

    同一个目标下、同一条路径上的同一个名字，永远得到同一个 id —— 因此再生成是
    「更新」而不是「新增」，`origin=adjusted` 的保护规则也才有稳定的作用对象。
    """
    seed = f"{goal_id}/{normalize_name(path)}/{normalize_name(name)}"
    return "cap_" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:20]


def assessment_id(
    user_id: str,
    goal_id: str,
    capability_id_: str,
    status: str,
    claim_ids: list[str],
    dimension: str | None = None,
    level: int | None = None,
) -> str:
    """assessment 的稳定逻辑标识：由**判定对象 + 维度 + 证据集 + 等级**派生。

    * 同一（能力点 / 维度 / 证据集 / 状态 / 等级）→ 同一 id（重复运行幂等）；
    * **等级变化 = 新 id**：反向证据或新证据改变评定结果时产生新行，
      旧行作为历史保留（history + current view 的同源纪律）；
    * 草案与评定是**不同的行**（状态与维度不同）—— 评定写入不覆盖旧草案。
    """
    seed = "/".join(
        [
            user_id,
            goal_id,
            capability_id_,
            status,
            ",".join(sorted(claim_ids)),
            dimension or "",
            "" if level is None else str(level),
        ]
    )
    return "asm_" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:20]


class GrowthStoreError(RuntimeError):
    """g_ 表族的写入违反了已冻结的数据语义。"""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise GrowthStoreError(message)


class GrowthStore:
    """`g_` 表族的建表与读写。

    与 evkg 的 `KnowledgeStore` 不同，这里提供 `close()` 与上下文管理器 ——
    M1-g 记录过「无 close() 导致 Windows 锁库」的上游缺陷（§7-10），
    自己的存储层不应重蹈。
    """

    def __init__(self, path: str | None = None):
        self.path = str(path or default_db_path())
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, check_same_thread=False)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA busy_timeout=30000")
        self.db.row_factory = sqlite3.Row
        self._migrate()

    # -- 生命周期 ---------------------------------------------------------

    def close(self) -> None:
        self.db.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    # -- 建表 -------------------------------------------------------------

    def _migrate(self) -> None:
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS g_users (
                id TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS g_goals (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                title TEXT NOT NULL,
                direction TEXT,
                purpose TEXT,
                horizon TEXT,
                measurable_result TEXT,
                status TEXT NOT NULL,
                source_quote TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS g_goal_clarifications (
                id TEXT PRIMARY KEY,
                goal_id TEXT NOT NULL,
                round INTEGER NOT NULL,
                question TEXT NOT NULL,
                answer TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(goal_id, round)
            );
            CREATE TABLE IF NOT EXISTS g_capabilities (
                id TEXT PRIMARY KEY,
                goal_id TEXT NOT NULL,
                parent_id TEXT,
                name TEXT NOT NULL,
                path TEXT NOT NULL,
                depth INTEGER NOT NULL,
                target_level INTEGER,
                origin TEXT NOT NULL DEFAULT 'generated',
                verification_status TEXT NOT NULL DEFAULT 'unverified',
                source_note TEXT,
                adjustment_note TEXT,
                generated_by_run_id TEXT,
                current_level INTEGER,
                current_level_status TEXT NOT NULL DEFAULT 'unassessed',
                current_level_understanding INTEGER,
                current_level_practice INTEGER,
                weight REAL,
                generation_id TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(goal_id, path)
            );
            CREATE TABLE IF NOT EXISTS g_capability_claims (
                capability_id TEXT NOT NULL,
                claim_id TEXT NOT NULL,
                role TEXT NOT NULL,
                rationale TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (capability_id, claim_id, role)
            );
            CREATE TABLE IF NOT EXISTS g_assessments (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                goal_id TEXT NOT NULL,
                capability_id TEXT NOT NULL,
                dimension TEXT,
                status TEXT NOT NULL,
                level INTEGER,
                rubric_json TEXT,
                rationale TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS g_agent_runs (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                agent TEXT NOT NULL,
                status TEXT NOT NULL,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                model_source TEXT NOT NULL,
                goal_id TEXT,
                correlation_id TEXT,
                input TEXT,
                tool_calls_json TEXT,
                output TEXT,
                error TEXT,
                tokens INTEGER,
                latency_ms INTEGER,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS g_gaps (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                goal_id TEXT NOT NULL,
                capability_id TEXT NOT NULL,
                dimension TEXT NOT NULL,
                current_level INTEGER,
                target_level INTEGER,
                severity TEXT NOT NULL,
                rationale TEXT NOT NULL,
                assessment_id TEXT,
                status TEXT NOT NULL DEFAULT 'open',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(capability_id, dimension)
            );
            CREATE TABLE IF NOT EXISTS g_tasks (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                goal_id TEXT NOT NULL,
                capability_id TEXT NOT NULL,
                gap_id TEXT NOT NULL,
                title TEXT NOT NULL,
                objective TEXT NOT NULL,
                deliverable_type TEXT NOT NULL,
                est_minutes INTEGER NOT NULL,
                acceptance_type TEXT NOT NULL,
                acceptance TEXT NOT NULL,
                origin TEXT NOT NULL DEFAULT 'generated',
                generated_by_run_id TEXT,
                status TEXT NOT NULL DEFAULT 'proposed',
                blocked_reason TEXT,
                abandoned_reason TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS g_task_submissions (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                source_id TEXT NOT NULL,
                note TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(task_id, source_id)
            );
            CREATE TABLE IF NOT EXISTS g_events (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                severity TEXT NOT NULL DEFAULT 'info',
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        # 已有库的列迁移（CREATE TABLE IF NOT EXISTS 不会补列）：
        # history + current view（M4-PLAN v1.0 §4）需要两个生命周期字段。
        columns = {
            row[1] for row in self.db.execute("PRAGMA table_info(g_capabilities)").fetchall()
        }
        if "generation_id" not in columns:
            self.db.execute("ALTER TABLE g_capabilities ADD COLUMN generation_id TEXT")
        if "status" not in columns:
            self.db.execute(
                "ALTER TABLE g_capabilities ADD COLUMN status TEXT NOT NULL DEFAULT 'active'"
            )
        assessment_columns = {
            row[1] for row in self.db.execute("PRAGMA table_info(g_assessments)").fetchall()
        }
        if "dimension" not in assessment_columns:
            self.db.execute("ALTER TABLE g_assessments ADD COLUMN dimension TEXT")
        # M4-d：维度化等级列（两个独立维度，替代 legacy 单值 current_level）。
        if "current_level_understanding" not in columns:
            self.db.execute(
                "ALTER TABLE g_capabilities ADD COLUMN current_level_understanding INTEGER"
            )
        if "current_level_practice" not in columns:
            self.db.execute(
                "ALTER TABLE g_capabilities ADD COLUMN current_level_practice INTEGER"
            )
        # M4-e：g_gaps 的早期形状（ARCHITECTURE §4.3 只有 id/capability_id/...）补维度列。
        gap_columns = {
            row[1] for row in self.db.execute("PRAGMA table_info(g_gaps)").fetchall()
        }
        if gap_columns and "dimension" not in gap_columns:
            self.db.execute("ALTER TABLE g_gaps ADD COLUMN dimension TEXT")
        if gap_columns and "user_id" not in gap_columns:
            self.db.execute("ALTER TABLE g_gaps ADD COLUMN user_id TEXT NOT NULL DEFAULT 'local'")
        if gap_columns and "goal_id" not in gap_columns:
            self.db.execute("ALTER TABLE g_gaps ADD COLUMN goal_id TEXT NOT NULL DEFAULT ''")
        if gap_columns and "assessment_id" not in gap_columns:
            self.db.execute("ALTER TABLE g_gaps ADD COLUMN assessment_id TEXT")
        if gap_columns and "updated_at" not in gap_columns:
            self.db.execute("ALTER TABLE g_gaps ADD COLUMN updated_at TEXT")
        self.db.commit()

    # -- g_users ----------------------------------------------------------

    def upsert_user(self, user_id: str, display_name: str) -> None:
        self.db.execute(
            "INSERT INTO g_users(id, display_name) VALUES(?, ?) "
            "ON CONFLICT(id) DO UPDATE SET display_name=excluded.display_name",
            (user_id, display_name),
        )
        self.db.commit()

    # -- g_goals ----------------------------------------------------------

    def save_goal(self, payload: dict) -> None:
        """upsert 一个目标。

        不变式：**一个被确认过的目标不能被清空**。若新状态是 `confirmed`，或旧状态
        已是 `confirmed` 且新状态不是 `archived`，四要素与 `source_quote` 必须齐全。
        """
        goal_id = payload.get("id")
        _require(bool(goal_id), "goal 缺少 id")
        status = payload.get("status")
        _require(status in GOAL_STATUSES, f"未知 goal 状态: {status!r}")

        existing = self.get_goal(goal_id)
        guarded = status == "confirmed" or (
            existing is not None and existing["status"] == "confirmed" and status != "archived"
        )
        if guarded:
            for field in GOAL_ELEMENTS:
                _require(
                    bool(str(payload.get(field) or "").strip()),
                    f"confirmed 目标缺少四要素之一: {field}",
                )
            _require(
                bool(str(payload.get("source_quote") or "").strip()),
                "confirmed 目标必须有 source_quote（用户确认的原话）",
            )

        self.db.execute(
            """
            INSERT INTO g_goals(id, user_id, title, direction, purpose, horizon,
                                measurable_result, status, source_quote)
            VALUES(:id, :user_id, :title, :direction, :purpose, :horizon,
                   :measurable_result, :status, :source_quote)
            ON CONFLICT(id) DO UPDATE SET
                title=excluded.title,
                direction=excluded.direction,
                purpose=excluded.purpose,
                horizon=excluded.horizon,
                measurable_result=excluded.measurable_result,
                status=excluded.status,
                source_quote=excluded.source_quote,
                updated_at=CURRENT_TIMESTAMP
            """,
            {
                "id": goal_id,
                "user_id": payload.get("user_id") or "local",
                "title": payload.get("title") or "",
                "direction": payload.get("direction"),
                "purpose": payload.get("purpose"),
                "horizon": payload.get("horizon"),
                "measurable_result": payload.get("measurable_result"),
                "status": status,
                "source_quote": payload.get("source_quote"),
            },
        )
        self.db.commit()

    def get_goal(self, goal_id: str) -> dict | None:
        row = self.db.execute("SELECT * FROM g_goals WHERE id=?", (goal_id,)).fetchone()
        return dict(row) if row else None

    def list_goals(self, user_id: str = "local") -> list[dict]:
        rows = self.db.execute(
            "SELECT * FROM g_goals WHERE user_id=? ORDER BY created_at, id", (user_id,)
        ).fetchall()
        return [dict(row) for row in rows]

    # -- g_goal_clarifications -------------------------------------------

    def add_clarification(self, goal_id: str, round: int, question: str, answer: str | None = None) -> str:
        """记录一轮问答。`round` 从 1 递增，由调用方显式给出（轮次上限是硬约束）。"""
        _require(round >= 1, "round 从 1 开始")
        clarification_id = f"clar_{goal_id}_{round:02d}"
        self.db.execute(
            "INSERT INTO g_goal_clarifications(id, goal_id, round, question, answer) "
            "VALUES(?,?,?,?,?) "
            "ON CONFLICT(goal_id, round) DO UPDATE SET question=excluded.question, answer=excluded.answer",
            (clarification_id, goal_id, round, question, answer),
        )
        self.db.commit()
        return clarification_id

    def list_clarifications(self, goal_id: str) -> list[dict]:
        rows = self.db.execute(
            "SELECT * FROM g_goal_clarifications WHERE goal_id=? ORDER BY round", (goal_id,)
        ).fetchall()
        return [dict(row) for row in rows]

    def next_round(self, goal_id: str) -> int:
        row = self.db.execute(
            "SELECT COALESCE(MAX(round), 0) AS last_round FROM g_goal_clarifications WHERE goal_id=?",
            (goal_id,),
        ).fetchone()
        return int(row["last_round"]) + 1

    # -- g_capabilities ---------------------------------------------------

    def upsert_capability(self, payload: dict) -> str:
        """写入/更新一个能力点；`origin=adjusted` 的行受保护（C1）。"""
        goal_id = payload.get("goal_id")
        path = payload.get("path")
        name = payload.get("name")
        _require(bool(goal_id and path and name), "capability 需要 goal_id / path / name")
        capability = payload.get("id") or capability_id(goal_id, path, name)
        origin = payload.get("origin", "generated")
        _require(origin in CAPABILITY_ORIGINS, f"未知 origin: {origin!r}")
        verification = payload.get("verification_status", "unverified")
        _require(verification in VERIFICATION_STATUSES, f"未知校验状态: {verification!r}")
        depth = int(payload.get("depth") or 0)
        _require(depth in (1, 2, 3), f"depth 必须是 1..3（三层树）: {depth}")
        level = payload.get("target_level")
        if level is not None:
            _require(
                TARGET_LEVEL_RANGE[0] <= int(level) <= TARGET_LEVEL_RANGE[1],
                f"target_level 必须在 {TARGET_LEVEL_RANGE[0]}..{TARGET_LEVEL_RANGE[1]}"
                f"（目标要求等级）: {level}",
            )

        _require(
            payload.get("current_level") is None,
            "禁止直接写入 current_level（legacy 列已 deprecated；M4-d 起使用维度化列，且只能经 apply_assessment_levels 回填）",
        )
        _require(
            payload.get("current_level_understanding") is None,
            "禁止通过 upsert_capability 写入 current_level_understanding（只能由 apply_assessment_levels 回填）",
        )
        _require(
            payload.get("current_level_practice") is None,
            "禁止通过 upsert_capability 写入 current_level_practice（只能由 apply_assessment_levels 回填）",
        )
        _require(
            payload.get("current_level_status", "unassessed") == "unassessed",
            "能力树生成时 current_level_status 只能是 unassessed（评估状态由 apply_assessment_levels 更新）",
        )
        status = payload.get("status", "active")
        _require(status in CAPABILITY_STATUSES, f"未知生命周期状态: {status!r}")
        generation_id = payload.get("generation_id")
        _require(
            generation_id is None or bool(str(generation_id).strip()),
            "generation_id 不能为空字符串",
        )

        existing = self.get_capability(capability)
        protected = existing is not None and existing["origin"] == "adjusted"
        if protected:
            payload = {
                **payload,
                "target_level": existing["target_level"],
                "adjustment_note": existing["adjustment_note"],
            }

        self.db.execute(
            """
            INSERT INTO g_capabilities(id, goal_id, parent_id, name, path, depth, target_level,
                                       origin, verification_status, source_note, adjustment_note,
                                       generated_by_run_id, current_level, current_level_status, weight,
                                       generation_id, status)
            VALUES(:id, :goal_id, :parent_id, :name, :path, :depth, :target_level,
                   :origin, :verification_status, :source_note, :adjustment_note,
                   :generated_by_run_id, NULL, 'unassessed', :weight,
                   :generation_id, :status)
            ON CONFLICT(id) DO UPDATE SET
                parent_id=excluded.parent_id,
                depth=excluded.depth,
                target_level=excluded.target_level,
                origin=excluded.origin,
                verification_status=excluded.verification_status,
                source_note=excluded.source_note,
                adjustment_note=excluded.adjustment_note,
                generated_by_run_id=excluded.generated_by_run_id,
                weight=excluded.weight,
                generation_id=COALESCE(excluded.generation_id, g_capabilities.generation_id),
                status=excluded.status,
                updated_at=CURRENT_TIMESTAMP
            """,
            {
                "id": capability,
                "goal_id": goal_id,
                "parent_id": payload.get("parent_id"),
                "name": name,
                "path": path,
                "depth": depth,
                "target_level": payload.get("target_level"),
                "origin": "adjusted" if protected else origin,
                "verification_status": verification,
                "source_note": payload.get("source_note"),
                "adjustment_note": payload.get("adjustment_note"),
                "generated_by_run_id": payload.get("generated_by_run_id"),
                "weight": payload.get("weight"),
                "generation_id": generation_id,
                "status": status,
            },
        )
        self.db.commit()
        return capability

    def adjust_capability(self, capability: str, target_level: int, note: str) -> None:
        """人工调整目标等级（必须留下修改来源；`origin` 转为 `adjusted`）。"""
        _require(
            TARGET_LEVEL_RANGE[0] <= int(target_level) <= TARGET_LEVEL_RANGE[1],
            f"target_level 必须在 {TARGET_LEVEL_RANGE[0]}..{TARGET_LEVEL_RANGE[1]}",
        )
        _require(bool((note or "").strip()), "人工调整必须写明来源/理由（adjustment_note）")
        cursor = self.db.execute(
            "UPDATE g_capabilities SET target_level=?, adjustment_note=?, origin='adjusted', "
            "updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (int(target_level), note.strip(), capability),
        )
        _require(cursor.rowcount == 1, f"未知能力点: {capability}")
        self.db.commit()

    def get_capability(self, capability: str) -> dict | None:
        row = self.db.execute("SELECT * FROM g_capabilities WHERE id=?", (capability,)).fetchone()
        return dict(row) if row else None

    def get_capability_by_path(self, goal_id: str, path: str) -> dict | None:
        """按（目标 + 路径）取能力点 —— LLM 提议只用路径引用，闸门据此解析成稳定 id。"""
        row = self.db.execute(
            "SELECT * FROM g_capabilities WHERE goal_id=? AND path=?", (goal_id, path)
        ).fetchone()
        return dict(row) if row else None

    def list_capabilities(self, goal_id: str, *, status: str | None = None) -> list[dict]:
        sql = "SELECT * FROM g_capabilities WHERE goal_id=?"
        params: list[Any] = [goal_id]
        if status is not None:
            _require(status in CAPABILITY_STATUSES, f"未知生命周期状态: {status!r}")
            sql += " AND status=?"
            params.append(status)
        sql += " ORDER BY path"
        rows = self.db.execute(sql, tuple(params)).fetchall()
        return [dict(row) for row in rows]

    def set_capability_status(self, capability: str, status: str, *, generation_id: str | None = None) -> None:
        """显式改变能力节点生命周期（人工归档等）；不删除任何行。"""
        _require(status in CAPABILITY_STATUSES, f"未知生命周期状态: {status!r}")
        cursor = self.db.execute(
            "UPDATE g_capabilities SET status=?, generation_id=COALESCE(?, generation_id), "
            "updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (status, generation_id, capability),
        )
        _require(cursor.rowcount == 1, f"未知能力点: {capability}")
        self.db.commit()

    def supersede_missing(
        self, goal_id: str, active_capability_ids: list[str], *, generation_id: str | None = None
    ) -> list[str]:
        """history + current view：再生成后，不在新树中的 `generated` 节点标记为 `superseded`。

        规则（M4-PLAN v1.0 §4，用户冻结）：

        * **不删除历史**（只改状态）；
        * `adjusted` 节点**不自动降级**（用户意志优先，延续 C1）；
        * 已经 `superseded` / `archived` 的节点不再改动。

        返回本次被标记的 id 列表。当前视图由 `list_capabilities(goal_id, status="active")` 得到。
        """
        active = set(active_capability_ids)
        marked: list[str] = []
        for row in self.list_capabilities(goal_id):
            if row["id"] in active or row["origin"] == "adjusted" or row["status"] != "active":
                continue
            cursor = self.db.execute(
                "UPDATE g_capabilities SET status='superseded', "
                "generation_id=COALESCE(?, generation_id), updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (generation_id, row["id"]),
            )
            if cursor.rowcount:
                marked.append(row["id"])
        self.db.commit()
        return marked

    # -- g_capability_claims / g_assessments（M4-a 契约）-------------------

    def link_capability_claim(
        self, capability_id: str, claim_id: str, *, role: str = "supports", rationale: str
    ) -> None:
        """能力点 ↔ 主张的显式绑定（桥表；M4-PLAN v1.0 §6 的映射落库）。

        规则：角色必须合法、能力点必须存在、`rationale` 必填 —— 映射必须可解释，
        "为什么这条主张挂在这个能力点上"是审计的一部分（提议与拒绝都留档）。
        """
        _require(role in CLAIM_ROLES, f"未知桥表角色: {role!r}")
        _require(bool(claim_id), "桥表需要 claim_id")
        _require(self.get_capability(capability_id) is not None, f"未知能力点: {capability_id}")
        note = (rationale or "").strip()
        _require(bool(note), "能力点-主张绑定必须写明 rationale（映射要可解释）")
        self.db.execute(
            "INSERT OR REPLACE INTO g_capability_claims(capability_id, claim_id, role, rationale) "
            "VALUES(?,?,?,?)",
            (capability_id, claim_id, role, note),
        )
        self.db.commit()

    def list_capability_claims(
        self, *, capability_id: str | None = None, role: str | None = None
    ) -> list[dict]:
        sql = "SELECT * FROM g_capability_claims WHERE 1=1"
        params: list[Any] = []
        if capability_id:
            sql += " AND capability_id=?"
            params.append(capability_id)
        if role:
            _require(role in CLAIM_ROLES, f"未知桥表角色: {role!r}")
            sql += " AND role=?"
            params.append(role)
        sql += " ORDER BY capability_id, claim_id"
        return [dict(row) for row in self.db.execute(sql, tuple(params)).fetchall()]

    def save_assessment_draft(self, payload: dict) -> str:
        """写入一份 assessment **草案**（M4-a：只有 `draft` / `insufficient_evidence`，无等级）。

        不变式（测试锁定）：

        * `level` 必须是 NULL —— 星级算法不在本步；写入任何数字都报错
          （沿用「缺失不得伪装成数字」的纪律，也防止在没有规则时手填等级）；
        * 能力点必须存在，且 `goal_id` 与能力点一致（跨表族引用由应用层保证）；
        * 状态只允许 `ASSESSMENT_STATUSES`；`rationale` 必填（草案必须说明为什么）。
        """
        capability_id_ = payload.get("capability_id")
        _require(bool(capability_id_), "assessment 需要 capability_id")
        capability = self.get_capability(capability_id_)
        _require(capability is not None, f"未知能力点: {capability_id_}")
        goal_id = payload.get("goal_id") or capability["goal_id"]
        _require(goal_id == capability["goal_id"], "assessment 的 goal_id 必须与能力点一致")
        status = payload.get("status")
        _require(
            status in DRAFT_STATUSES,
            f"未知 assessment 状态: {status!r}（草案只允许 {DRAFT_STATUSES}；评定走 save_assessment）",
        )
        _require(
            payload.get("dimension") is None,
            "草案不带维度：草案是 M4-a/b 的形态，维度化评定走 save_assessment",
        )
        _require(
            payload.get("level") is None,
            "草案不得写入星级（level）：定级属评定步骤（M4-c），本路径只产出草案",
        )
        rationale = (payload.get("rationale") or "").strip()
        _require(bool(rationale), "assessment 草案必须写明 rationale")
        user_id = payload.get("user_id") or "local"
        claim_ids = [str(item) for item in (payload.get("claim_ids") or [])]
        identifier = payload.get("id") or assessment_id(
            user_id, goal_id, capability_id_, status, claim_ids
        )
        self.db.execute(
            """
            INSERT INTO g_assessments(id, user_id, goal_id, capability_id, status, level,
                                      rubric_json, rationale)
            VALUES(:id, :user_id, :goal_id, :capability_id, :status, NULL,
                   :rubric_json, :rationale)
            ON CONFLICT(id) DO UPDATE SET
                status=excluded.status,
                rubric_json=excluded.rubric_json,
                rationale=excluded.rationale,
                updated_at=CURRENT_TIMESTAMP
            """,
            {
                "id": identifier,
                "user_id": user_id,
                "goal_id": goal_id,
                "capability_id": capability_id_,
                "status": status,
                "rubric_json": dumps(payload.get("rubric") or {}),
                "rationale": rationale,
            },
        )
        self.db.commit()
        return identifier

    def save_assessment(self, payload: dict) -> str:
        """写入一份**维度化评定**（M4-c：`rated` 或 `insufficient_evidence`）。

        不变式（测试锁定）：

        * `dimension` 必须是 `ASSESSMENT_DIMENSIONS` 之一（理解 / 实践是两个独立维度）；
        * `status='rated'` 时才允许且必须给出 `level ∈ LEVEL_RANGE`；
        * `status='insufficient_evidence'` 时 `level` 必须为 NULL（缺失 ≠ 低分）；
        * `rubric` / `rationale` 必填（评定必须可解释、可审计）；
        * **不覆盖旧草案**：id 由「对象 + 维度 + 证据集 + 状态 + 等级」派生，
          等级变化即新行（历史保留；当前视图用 `latest_assessment` 查询解决）。
        """
        capability_id_ = payload.get("capability_id")
        _require(bool(capability_id_), "assessment 需要 capability_id")
        capability = self.get_capability(capability_id_)
        _require(capability is not None, f"未知能力点: {capability_id_}")
        goal_id = payload.get("goal_id") or capability["goal_id"]
        _require(goal_id == capability["goal_id"], "assessment 的 goal_id 必须与能力点一致")
        dimension = payload.get("dimension")
        _require(
            dimension in ASSESSMENT_DIMENSIONS,
            f"未知维度: {dimension!r}（只允许 {ASSESSMENT_DIMENSIONS}）",
        )
        status = payload.get("status")
        _require(status in ("rated", "insufficient_evidence"), f"未知评定状态: {status!r}")
        level = payload.get("level")
        if status == "rated":
            _require(
                isinstance(level, int)
                and not isinstance(level, bool)
                and LEVEL_RANGE[0] <= level <= LEVEL_RANGE[1],
                f"rated 必须给出 {LEVEL_RANGE[0]}..{LEVEL_RANGE[1]} 的星级: {level!r}",
            )
        else:
            _require(level is None, "insufficient_evidence 不得写 level（缺失 ≠ 低分）")
        rationale = (payload.get("rationale") or "").strip()
        _require(bool(rationale), "评定必须写明 rationale")
        rubric = payload.get("rubric")
        _require(
            isinstance(rubric, dict) and bool(rubric),
            "评定必须携带 rubric（可解释、可审计）",
        )
        user_id = payload.get("user_id") or "local"
        claim_ids = [str(item) for item in (payload.get("claim_ids") or [])]
        identifier = payload.get("id") or assessment_id(
            user_id, goal_id, capability_id_, status, claim_ids, dimension, level
        )
        self.db.execute(
            """
            INSERT INTO g_assessments(id, user_id, goal_id, capability_id, dimension, status,
                                      level, rubric_json, rationale)
            VALUES(:id, :user_id, :goal_id, :capability_id, :dimension, :status,
                   :level, :rubric_json, :rationale)
            ON CONFLICT(id) DO UPDATE SET
                rubric_json=excluded.rubric_json,
                rationale=excluded.rationale,
                updated_at=CURRENT_TIMESTAMP
            """,
            {
                "id": identifier,
                "user_id": user_id,
                "goal_id": goal_id,
                "capability_id": capability_id_,
                "dimension": dimension,
                "status": status,
                "level": level,
                "rubric_json": dumps(rubric),
                "rationale": rationale,
            },
        )
        self.db.commit()
        return identifier

    def get_assessment(self, assessment: str) -> dict | None:
        row = self.db.execute("SELECT * FROM g_assessments WHERE id=?", (assessment,)).fetchone()
        return dict(row) if row else None

    def list_assessments(
        self,
        *,
        capability_id: str | None = None,
        goal_id: str | None = None,
        status: str | None = None,
        dimension: str | None = None,
    ) -> list[dict]:
        sql = "SELECT * FROM g_assessments WHERE 1=1"
        params: list[Any] = []
        if capability_id:
            sql += " AND capability_id=?"
            params.append(capability_id)
        if goal_id:
            sql += " AND goal_id=?"
            params.append(goal_id)
        if status:
            sql += " AND status=?"
            params.append(status)
        if dimension:
            _require(dimension in ASSESSMENT_DIMENSIONS, f"未知维度: {dimension!r}")
            sql += " AND dimension=?"
            params.append(dimension)
        sql += " ORDER BY capability_id, created_at, id"
        return [dict(row) for row in self.db.execute(sql, tuple(params)).fetchall()]

    def latest_assessment(self, capability_id: str, dimension: str) -> dict | None:
        """当前视图：某（能力点 × 维度）最近一次**评定结果**。

        `draft` 不算当前视图（草案不是评定结果）；历史用 `list_assessments` 查
        —— 「draft → rated → history preserved」由查询规则解决，不靠覆盖写入。
        """
        _require(dimension in ASSESSMENT_DIMENSIONS, f"未知维度: {dimension!r}")
        row = self.db.execute(
            "SELECT * FROM g_assessments WHERE capability_id=? AND dimension=? "
            "AND status IN ('rated','insufficient_evidence') "
            "ORDER BY created_at DESC, rowid DESC LIMIT 1",
            (capability_id, dimension),
        ).fetchone()
        return dict(row) if row else None

    def expected_assessment_levels(self, capability_id: str) -> dict:
        """从评定行**重算**该能力点的（理解 / 实践 / 状态）——回填与校验共用同一计算。

        这是"评级结果是可重算派生数据"（M4-c 结论 4）的落地：任何时刻，
        `g_capabilities` 上的回填值都必须等于这里的重算结果。
        """
        capability = self.get_capability(capability_id)
        _require(capability is not None, f"未知能力点: {capability_id}")
        levels: dict[str, int | None] = {}
        for dimension in ASSESSMENT_DIMENSIONS:
            row = self.latest_assessment(capability_id, dimension)
            levels[dimension] = row["level"] if row and row["status"] == "rated" else None
        status = "assessed" if any(value is not None for value in levels.values()) else "unassessed"
        return {**levels, "status": status}

    def apply_assessment_levels(self, capability_id: str) -> dict:
        """从 latest_assessment 回填维度化等级列（M4-d 显式方法）。

        规则（用户 2026-10-03 冻结）：
        - 读取两维度的最新评定结果（rated / insufficient_evidence）；
        - 回填 `current_level_understanding` / `current_level_practice`
          （rated → level 数字；insufficient_evidence / 无评定 → NULL）；
        - 更新 `current_level_status`：两维度均 NULL → `unassessed`，
          至少一个非 NULL → `assessed`（允许"理解有、实践无"的部分评估状态）；
        - legacy `current_level` 保持 NULL 不写（deprecated，M4-d 起停用）。

        本方法是**唯一可写维度化等级列的路径** —— upsert/adjust 直接写入会报错。
        返回本次写入的（重算）结果，便于调用方对照。
        """
        expected = self.expected_assessment_levels(capability_id)
        self.db.execute(
            "UPDATE g_capabilities SET current_level_understanding=?, current_level_practice=?, "
            "current_level_status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (
                expected["understanding"],
                expected["practice"],
                expected["status"],
                capability_id,
            ),
        )
        self.db.commit()
        return expected

    def verify_assessment_levels(self, capability_id: str) -> dict:
        """重建校验：回填列必须等于从评定行重算的结果（不一致即报告差异）。"""
        expected = self.expected_assessment_levels(capability_id)
        capability = self.get_capability(capability_id)
        stored = {
            "understanding": capability["current_level_understanding"],
            "practice": capability["current_level_practice"],
            "status": capability["current_level_status"],
        }
        return {"consistent": stored == expected, "expected": expected, "stored": stored}

    # -- g_gaps -----------------------------------------------------------

    def expected_gaps(self, capability_id: str) -> list[dict]:
        """从**已存在的评定行**重算缺口（M4-e 冻结规则）。

        * 无评定（含只有草案）→ 该维度**不产生缺口**（未评估 ≠ 缺口）；
        * `insufficient_evidence` → `evidence_gap`（缺可核验证据，不判定为低能力）；
        * `rated` 且低于目标 → `level_gap_1` / `level_gap_2plus`（差 1 / 差 ≥2）；
        * `rated` 且达到/超过目标 → 无缺口（已有行会由 `apply_gaps` 置 `closed`）。

        `rationale` 只由「等级对照 + `rubric.gaps` 原文」拼成 —— 不生成
        额外的能力判断（M4-d 冻结的 gaps-only 纪律）。
        """
        capability = self.get_capability(capability_id)
        _require(capability is not None, f"未知能力点: {capability_id}")
        target = capability["target_level"]
        gaps: list[dict] = []
        for dimension in ASSESSMENT_DIMENSIONS:
            row = self.latest_assessment(capability_id, dimension)
            if row is None:
                continue
            rubric = json.loads(row["rubric_json"]) if row.get("rubric_json") else {}
            texts = [str(item) for item in (rubric.get("gaps") or [])]
            label = "理解" if dimension == "understanding" else "实践"
            if row["status"] == "insufficient_evidence":
                severity = "evidence_gap"
                current = None
                rationale = f"缺少可核验的{label}证据（证据不足，不判定为低能力）"
            else:
                current = row["level"]
                if target is None or current >= target:
                    continue
                difference = target - current
                severity = "level_gap_1" if difference == 1 else "level_gap_2plus"
                rationale = f"{label} {current} 级，目标 {target} 级（差 {difference} 级）"
            if texts:
                rationale += "；缺口：" + "；".join(texts)
            gaps.append(
                {
                    "id": gap_id(capability_id, dimension),
                    "user_id": row["user_id"],
                    "goal_id": row["goal_id"],
                    "capability_id": capability_id,
                    "dimension": dimension,
                    "current_level": current,
                    "target_level": target,
                    "severity": severity,
                    "rationale": rationale,
                    "assessment_id": row["id"],
                    "status": "open",
                }
            )
        return gaps

    def apply_gaps(self, capability_id: str) -> dict:
        """缺口回填（**唯一**可写 `g_gaps` 的路径）：重算 → upsert `open` → 失效行 `closed`。

        与 `apply_assessment_levels` 同款纪律：缺口是派生数据，任何时刻都必须能从
        评定行重算；同一（能力点 × 维度）最多一条 `open` 行（UNIQUE 约束兜底）。
        """
        expected = self.expected_gaps(capability_id)
        keep = {item["id"] for item in expected}
        for item in expected:
            self.db.execute(
                """
                INSERT INTO g_gaps(id, user_id, goal_id, capability_id, dimension,
                                   current_level, target_level, severity, rationale,
                                   assessment_id, status)
                VALUES(:id, :user_id, :goal_id, :capability_id, :dimension,
                       :current_level, :target_level, :severity, :rationale,
                       :assessment_id, 'open')
                ON CONFLICT(id) DO UPDATE SET
                    current_level=excluded.current_level,
                    target_level=excluded.target_level,
                    severity=excluded.severity,
                    rationale=excluded.rationale,
                    assessment_id=excluded.assessment_id,
                    status='open',
                    updated_at=CURRENT_TIMESTAMP
                """,
                item,
            )
        stale = [
            row["id"]
            for row in self.db.execute(
                "SELECT id FROM g_gaps WHERE capability_id=? AND status='open'",
                (capability_id,),
            ).fetchall()
            if row["id"] not in keep
        ]
        for identifier in stale:
            self.db.execute(
                "UPDATE g_gaps SET status='closed', updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (identifier,),
            )
        self.db.commit()
        return {"gaps": expected, "closed": stale}

    def verify_gaps(self, capability_id: str) -> dict:
        """重建校验：`open` 缺口行必须等于从评定行重算的结果（含"多出的行"）。"""
        expected = self.expected_gaps(capability_id)
        fields = (
            "id",
            "dimension",
            "current_level",
            "target_level",
            "severity",
            "rationale",
            "assessment_id",
            "status",
        )
        stored = [
            {key: row[key] for key in fields}
            for row in self.db.execute(
                "SELECT * FROM g_gaps WHERE capability_id=? AND status='open' "
                "ORDER BY dimension",
                (capability_id,),
            ).fetchall()
        ]
        expected_sorted = sorted(
            ({key: item[key] for key in fields} for item in expected),
            key=lambda item: item["dimension"],
        )
        return {
            "consistent": stored == expected_sorted,
            "expected": expected_sorted,
            "stored": stored,
        }

    def list_gaps(
        self, *, capability_id: str | None = None, status: str | None = None
    ) -> list[dict]:
        if status is not None:
            _require(status in GAP_STATUSES, f"未知缺口状态: {status!r}")
        sql = "SELECT * FROM g_gaps WHERE 1=1"
        params: list[Any] = []
        if capability_id:
            sql += " AND capability_id=?"
            params.append(capability_id)
        if status:
            sql += " AND status=?"
            params.append(status)
        sql += " ORDER BY capability_id, dimension"
        return [dict(row) for row in self.db.execute(sql, tuple(params)).fetchall()]

    # -- g_tasks / g_task_submissions / g_events（M5-a 契约与状态机）--------

    def create_task(self, payload: dict) -> str:
        """创建一个任务（`status='proposed'`）。

        契约（`M5-PLAN.md` §2.1/§3，用户冻结）：

        * **主缺口必填**且必须是 `open`；能力点必须 `active`（无缺口不生成任务）；
        * **维度 ↔ 交付物**：`understanding` 缺口只允许 `probe_answer`；
          `practice` 缺口只允许 `markdown/code/archive`；
        * `acceptance` 非空且不得命中不可验收反例模式（"去学习 X" 式）；
        * `est_minutes` 为 10–600 的整数；
        * **去重**：同一缺口已有未关闭任务（`proposed/active/blocked`）→ 拒绝；
        * **任务不含等级/分值字段**（Task 不是能力判断，用户约束 ①）。
        """
        gap_id_ = str(payload.get("gap_id") or "")
        _require(bool(gap_id_), "task 需要 gap_id（主缺口，不得无缺口生成）")
        gap = self.db.execute("SELECT * FROM g_gaps WHERE id=?", (gap_id_,)).fetchone()
        _require(gap is not None, f"未知缺口: {gap_id_}")
        _require(
            gap["status"] == "open",
            f"只对 open 缺口生成任务（当前 {gap['status']}）",
        )
        capability = self.get_capability(gap["capability_id"])
        _require(capability is not None, f"缺口引用的能力点不存在: {gap['capability_id']}")
        _require(
            capability["status"] == "active",
            f"只对 active 能力点生成任务（当前 {capability['status']}）",
        )
        deliverable_type = str(payload.get("deliverable_type") or "")
        _require(
            deliverable_type in TASK_DELIVERABLE_TYPES,
            f"未知交付物类型: {deliverable_type!r}（只允许 {TASK_DELIVERABLE_TYPES}）",
        )
        allowed = DIMENSION_DELIVERABLE_TYPES[gap["dimension"]]
        _require(
            deliverable_type in allowed,
            f"{gap['dimension']} 缺口的交付物只允许 {allowed}：收到 {deliverable_type!r}",
        )
        title = str(payload.get("title") or "").strip()
        objective = str(payload.get("objective") or "").strip()
        _require(bool(title), "task 需要 title")
        _require(bool(objective), "task 需要 objective（必须表述'产出什么'）")
        acceptance_type = str(payload.get("acceptance_type") or "")
        _require(
            acceptance_type in TASK_ACCEPTANCE_TYPES,
            f"未知验收方式: {acceptance_type!r}（只允许 {TASK_ACCEPTANCE_TYPES}）",
        )
        acceptance = str(payload.get("acceptance") or "").strip()
        _require(len(acceptance) >= 8, "acceptance 必须写明可操作的验收方式（≥8 字符）")
        for text, label in ((title, "title"), (objective, "objective"), (acceptance, "acceptance")):
            hit = next((marker for marker in TASK_ACCEPTANCE_ANTI_PATTERNS if marker in text), None)
            _require(
                hit is None,
                f"不可验收的表述（命中反例 {hit!r}）：任务必须定义产出物与验收方式，"
                "而不是'去学习 X'（PRD §12）",
            )
        est_minutes = payload.get("est_minutes")
        _require(
            isinstance(est_minutes, int)
            and not isinstance(est_minutes, bool)
            and TASK_EST_MINUTES_RANGE[0] <= est_minutes <= TASK_EST_MINUTES_RANGE[1],
            f"est_minutes 必须是 {TASK_EST_MINUTES_RANGE[0]}..{TASK_EST_MINUTES_RANGE[1]} 的整数: {est_minutes!r}",
        )
        origin = payload.get("origin", "generated")
        _require(origin in CAPABILITY_ORIGINS, f"未知 origin: {origin!r}")
        run_id = str(payload.get("generated_by_run_id") or "manual")

        existing = self.db.execute(
            "SELECT id, status FROM g_tasks WHERE gap_id=? AND status IN ('proposed','active','blocked')",
            (gap_id_,),
        ).fetchone()
        if existing is not None:
            raise GrowthStoreError(
                f"该缺口已有未关闭任务（{existing['id']}，{existing['status']}）—— 不重复生成"
            )
        seq = self.db.execute(
            "SELECT COUNT(*) FROM g_tasks WHERE gap_id=?", (gap_id_,)
        ).fetchone()[0]
        identifier = payload.get("id") or task_id(gap_id_, deliverable_type, run_id, seq)

        self.db.execute(
            """
            INSERT INTO g_tasks(id, user_id, goal_id, capability_id, gap_id, title, objective,
                                deliverable_type, est_minutes, acceptance_type, acceptance,
                                origin, generated_by_run_id, status)
            VALUES(:id, :user_id, :goal_id, :capability_id, :gap_id, :title, :objective,
                   :deliverable_type, :est_minutes, :acceptance_type, :acceptance,
                   :origin, :generated_by_run_id, 'proposed')
            """,
            {
                "id": identifier,
                "user_id": gap["user_id"],
                "goal_id": gap["goal_id"],
                "capability_id": gap["capability_id"],
                "gap_id": gap_id_,
                "title": title,
                "objective": objective,
                "deliverable_type": deliverable_type,
                "est_minutes": est_minutes,
                "acceptance_type": acceptance_type,
                "acceptance": acceptance,
                "origin": origin,
                "generated_by_run_id": run_id,
            },
        )
        self.db.commit()
        self._record_task_event(identifier, None, "proposed", None)
        return identifier

    def _record_task_event(self, task_id_: str, from_status: str | None, to_status: str, reason: str | None) -> str:
        payload = {"task_id": task_id_, "from": from_status, "to": to_status, "reason": reason}
        return self.write_event("task_status_changed", payload)

    def _transition(self, task_id_: str, to_status: str, *, reason: str | None = None) -> dict:
        task = self.get_task(task_id_)
        _require(task is not None, f"未知任务: {task_id_}")
        current = task["status"]
        allowed = TASK_TRANSITIONS.get(current, ())
        _require(
            to_status in allowed,
            f"非法状态转移: {current} → {to_status}（允许 {allowed}）",
        )
        if to_status in ("blocked", "abandoned"):
            _require(bool(str(reason or "").strip()), f"进入 {to_status} 必须给出 reason")
        column = ""
        params: list[Any] = [to_status]
        if to_status == "blocked":
            column = ", blocked_reason=?"
            params.append(str(reason).strip())
        if to_status == "abandoned":
            column = ", abandoned_reason=?"
            params.append(str(reason).strip())
        if to_status == "active":
            column = ", blocked_reason=NULL"
        params.append(task_id_)
        self.db.execute(
            f"UPDATE g_tasks SET status=?{column}, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            tuple(params),
        )
        self.db.commit()
        self._record_task_event(task_id_, current, to_status, reason)
        return self.get_task(task_id_)

    def activate_task(self, task_id_: str) -> dict:
        """`proposed → active`（M5 无 UI：由调用方显式确认）。"""
        return self._transition(task_id_, "active")

    def block_task(self, task_id_: str, reason: str) -> dict:
        """`active → blocked`（reason 必填）。"""
        return self._transition(task_id_, "blocked", reason=reason)

    def unblock_task(self, task_id_: str) -> dict:
        """`blocked → active`。"""
        return self._transition(task_id_, "active")

    def abandon_task(self, task_id_: str, reason: str) -> dict:
        """`proposed/active/blocked → abandoned`（reason 必填）。"""
        return self._transition(task_id_, "abandoned", reason=reason)

    def complete_task(self, task_id_: str, *, source_id: str, note: str | None = None) -> dict:
        """**`done` 的唯一入口**：提交产物（已有 source_id）→ 记录提交 + 置 `done`。

        * `source_id` 必须非空（指向 evkg sources）—— **存在性由调用方在证据层校验**
          （`GrowthStore` 只碰 `g_` 表，不读证据表族）；
        * 同一（任务 × 来源）重复提交命中同一行（幂等）；
        * 任务完成 **不等于** 能力提升：等级只能由 M4 规则引擎在
          `submission → evidence → claim → binding gate → assessment` 之后给出
          （用户约束 ②）。
        """
        task = self.get_task(task_id_)
        _require(task is not None, f"未知任务: {task_id_}")
        source_id_ = str(source_id or "").strip()
        _require(bool(source_id_), "complete_task 需要 source_id（提交必须产生证据来源）")
        _require(
            task["status"] == "active",
            f"只有 active 任务可以完成（当前 {task['status']}）—— 先 activate",
        )
        identifier = submission_id(task_id_, source_id_)
        self.db.execute(
            "INSERT INTO g_task_submissions(id, task_id, source_id, note) VALUES(?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET note=excluded.note",
            (identifier, task_id_, source_id_, note),
        )
        self.db.commit()
        self._transition(task_id_, "done")
        return {
            "task_id": task_id_,
            "submission_id": identifier,
            "source_id": source_id_,
            "status": "done",
        }

    def get_task(self, task_id_: str) -> dict | None:
        row = self.db.execute("SELECT * FROM g_tasks WHERE id=?", (task_id_,)).fetchone()
        return dict(row) if row else None

    def list_tasks(
        self,
        *,
        status: str | None = None,
        gap_id: str | None = None,
        capability_id: str | None = None,
    ) -> list[dict]:
        if status is not None:
            _require(status in TASK_STATUSES, f"未知任务状态: {status!r}")
        sql = "SELECT * FROM g_tasks WHERE 1=1"
        params: list[Any] = []
        if status:
            sql += " AND status=?"
            params.append(status)
        if gap_id:
            sql += " AND gap_id=?"
            params.append(gap_id)
        if capability_id:
            sql += " AND capability_id=?"
            params.append(capability_id)
        sql += " ORDER BY created_at, id"
        return [dict(row) for row in self.db.execute(sql, tuple(params)).fetchall()]

    def list_task_submissions(self, *, task_id: str | None = None) -> list[dict]:
        sql = "SELECT * FROM g_task_submissions WHERE 1=1"
        params: list[Any] = []
        if task_id:
            sql += " AND task_id=?"
            params.append(task_id)
        sql += " ORDER BY rowid"
        return [dict(row) for row in self.db.execute(sql, tuple(params)).fetchall()]

    # -- g_events ---------------------------------------------------------

    def write_event(self, kind: str, payload: dict, *, severity: str = "info") -> str:
        """写一条事件（append-only）。M5 冻结的 kind 见 `TASK_EVENT_KINDS`。"""
        _require(bool(str(kind or "").strip()), "event 需要 kind")
        body = dumps(payload or {})
        count = self.db.execute("SELECT COUNT(*) FROM g_events").fetchone()[0]
        identifier = "evt_" + hashlib.sha256(f"{kind}|{body}|{count}".encode()).hexdigest()[:20]
        self.db.execute(
            "INSERT INTO g_events(id, user_id, kind, severity, payload_json) VALUES(?,?,?,?,?)",
            (identifier, "local", kind, severity, body),
        )
        self.db.commit()
        return identifier

    def list_events(self, *, kind: str | None = None) -> list[dict]:
        sql = "SELECT * FROM g_events WHERE 1=1"
        params: list[Any] = []
        if kind:
            sql += " AND kind=?"
            params.append(kind)
        sql += " ORDER BY rowid"
        return [dict(row) for row in self.db.execute(sql, tuple(params)).fetchall()]

    # -- g_agent_runs -----------------------------------------------------

    def save_run(self, payload: dict) -> None:
        """记录一次 Agent 运行。

        不变式（C2）：`provider`/`model` 必填；`model_source='result'` 只能配
        `status='ok'`（来自实际返回值），`config_on_error` 只能配 `status='error'`。
        """
        status = payload.get("status")
        source = payload.get("model_source")
        _require(status in RUN_STATUSES, f"未知运行状态: {status!r}")
        _require(source in MODEL_SOURCES, f"未知 model_source: {source!r}")
        _require(
            (source == "result") == (status == "ok"),
            "model_source 与 status 不匹配：成功必须来自返回值，失败必须标注为配置值",
        )
        _require(bool(payload.get("provider")), "运行记录必须包含 provider")
        _require(bool(payload.get("model")), "运行记录必须包含 model")
        _require(bool(payload.get("id")), "运行记录必须包含 id")
        _require(bool(payload.get("agent")), "运行记录必须包含 agent")

        self.db.execute(
            """
            INSERT OR REPLACE INTO g_agent_runs(id, user_id, agent, status, provider, model,
                                                model_source, goal_id, correlation_id, input,
                                                tool_calls_json, output, error, tokens, latency_ms)
            VALUES(:id, :user_id, :agent, :status, :provider, :model,
                   :model_source, :goal_id, :correlation_id, :input,
                   :tool_calls_json, :output, :error, :tokens, :latency_ms)
            """,
            {
                "id": payload["id"],
                "user_id": payload.get("user_id") or "local",
                "agent": payload["agent"],
                "status": status,
                "provider": payload["provider"],
                "model": payload["model"],
                "model_source": source,
                "goal_id": payload.get("goal_id"),
                "correlation_id": payload.get("correlation_id"),
                "input": payload.get("input"),
                "tool_calls_json": payload.get("tool_calls_json"),
                "output": payload.get("output"),
                "error": payload.get("error"),
                "tokens": payload.get("tokens"),
                "latency_ms": payload.get("latency_ms"),
            },
        )
        self.db.commit()

    def get_run(self, run_id: str) -> dict | None:
        row = self.db.execute("SELECT * FROM g_agent_runs WHERE id=?", (run_id,)).fetchone()
        return dict(row) if row else None

    def list_runs(self, *, goal_id: str | None = None, agent: str | None = None) -> list[dict]:
        sql = "SELECT * FROM g_agent_runs WHERE 1=1"
        params: list[Any] = []
        if goal_id:
            sql += " AND goal_id=?"
            params.append(goal_id)
        if agent:
            sql += " AND agent=?"
            params.append(agent)
        sql += " ORDER BY created_at, id"
        return [dict(row) for row in self.db.execute(sql, tuple(params)).fetchall()]

    # -- 观测 -------------------------------------------------------------

    def counts(self) -> dict:
        tables = (
            "g_users",
            "g_goals",
            "g_goal_clarifications",
            "g_capabilities",
            "g_capability_claims",
            "g_assessments",
            "g_agent_runs",
        )
        return {
            table: self.db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in tables
        }


def dumps(value: Any) -> str:
    """把结构化输出序列化为可入库文本（非 JSON 类型退化为字符串）。"""
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    except TypeError:
        return str(value)
