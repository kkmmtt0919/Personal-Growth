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
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(goal_id, path)
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
                                       generated_by_run_id, current_level, current_level_status, weight)
            VALUES(:id, :goal_id, :parent_id, :name, :path, :depth, :target_level,
                   :origin, :verification_status, :source_note, :adjustment_note,
                   :generated_by_run_id, NULL, 'unassessed', :weight)
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

    def list_capabilities(self, goal_id: str) -> list[dict]:
        rows = self.db.execute(
            "SELECT * FROM g_capabilities WHERE goal_id=? ORDER BY path", (goal_id,)
        ).fetchall()
        return [dict(row) for row in rows]

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
        tables = ("g_users", "g_goals", "g_goal_clarifications", "g_capabilities", "g_agent_runs")
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
