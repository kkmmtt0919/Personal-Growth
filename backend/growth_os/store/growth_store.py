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
3. **未评估 ≠ 低等级**：`current_level` 在 M2 恒为 NULL，`current_level_status`
   恒为 `unassessed`；写入非空 `current_level` 会直接报错，而不是被静默接受
   （沿用 M1-b.5b「缺失不得伪装成数字」的语义）。
4. **M4-a 的生命周期与草案语义**：能力节点带 `generation_id` / `status`
   （history + current view，§4）；assessment 只允许草案状态且 `level` 恒为 NULL ——
   星级算法不在本步，写入任何等级数字都报错。
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

ASSESSMENT_DIMENSIONS = ("understanding", "practice")
"""两个独立维度（用户 2026-10-03 冻结）：理解与实践不合并成单一等级。"""

LEVEL_RANGE = (1, 5)
"""星级取值范围（PRD §9.1 五级）。"""

CLAIM_ROLES = ("supports", "gap")
"""`g_capability_claims` 桥表角色（ARCHITECTURE §4.3）。"""

GOAL_ELEMENTS = ("direction", "purpose", "horizon", "measurable_result")
"""confirmed goal 必须齐全的四要素：方向 / 目的 / 时间周期 / 可衡量结果。"""


def default_db_path() -> str:
    """`GROWTH_DB` 未设置时与证据库同文件（D2：单 SQLite，双表族）。"""
    return os.getenv("GROWTH_DB", "data/growth.db")


def normalize_name(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip().casefold()


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
            "M2 不得写入 current_level：现状一律为「尚未评估」，不得用任何数字（含 target_level）填充",
        )
        _require(
            payload.get("current_level_status", "unassessed") == "unassessed",
            "M2 的 current_level_status 只能是 unassessed",
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
