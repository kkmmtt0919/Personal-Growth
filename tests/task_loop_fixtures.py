"""M5-c 测试夹具：真实缺口场景（受控材料 → M4-e 编排 → open 缺口）+ 绑定提议对例。

材料为受控构造并如实标注（与 M5-b/G3-A 同款先例）：本夹具验证的是闭环机制
（证据 → claim → 绑定 → 重评 → 归因），不是"用户本人完成了任务"。
"""

from __future__ import annotations

import re
from pathlib import Path

from growth_os.assessment import assess_capability
from growth_os.evidence import adapter

GOAL_ID = "goal_m5c"

MATERIALS = {
    "m5c-notes.md": ("# 笔记\n\nRAG 检索流程整理：切分、向量化、召回、重排。\n", "uploaded_doc"),
    "m5c-repo.md": ("# 项目\n\n实现了一个最小检索服务与命令行入口。\n", "repo_artifact"),
}
"""受控材料：理解侧笔记（uploaded_doc）+ 实践侧项目文档（repo_artifact）。"""


def seed_scenario(store, estore, workdir: Path, *, second_capability: bool = False) -> dict:
    """构造目标树 + 受控材料 → M4-e 编排 → 两个 open 缺口（实践 3 / 理解 2，目标 4）。"""
    store.upsert_user("local", "本地用户")
    store.save_goal(
        {
            "id": GOAL_ID,
            "user_id": "local",
            "title": "成为 AI Agent 工程师",
            "direction": "AI 应用方向",
            "purpose": "求职",
            "horizon": "6 个月",
            "measurable_result": "完成一个可演示的 RAG 项目",
            "status": "confirmed",
            "source_quote": "我想成为 AI Agent 工程师",
        }
    )
    domain = store.upsert_capability(
        {"goal_id": GOAL_ID, "path": "AI Agent", "name": "AI Agent", "depth": 1, "target_level": 3}
    )
    group = store.upsert_capability(
        {
            "goal_id": GOAL_ID,
            "path": "AI Agent/工具与执行",
            "name": "工具与执行",
            "depth": 2,
            "parent_id": domain,
            "target_level": 3,
        }
    )
    capability = store.upsert_capability(
        {
            "goal_id": GOAL_ID,
            "path": "AI Agent/工具与执行/RAG 系统搭建与调优",
            "name": "RAG 系统搭建与调优",
            "depth": 3,
            "parent_id": group,
            "target_level": 4,
        }
    )
    other_capability = None
    if second_capability:
        other_capability = store.upsert_capability(
            {
                "goal_id": GOAL_ID,
                "path": "AI Agent/工具与执行/提示工程",
                "name": "提示工程",
                "depth": 3,
                "parent_id": group,
                "target_level": 3,
            }
        )

    def add_material(filename: str, content: str, evidence_type: str) -> dict:
        target = workdir / filename
        target.write_text(content, encoding="utf-8")
        ingested = adapter.ingest_document(
            target,
            store=estore,
            evidence_type=evidence_type,
            attribution="user_declared",
            extra_metadata={
                "growth_source_kind": "constructed_material",
                "growth_constructed": True,
                "growth_constructed_note": "M5-c 测试夹具（受控构造，如实标注）",
            },
        )
        passage_ids = [item.id for item in estore.get_passages(source_id=ingested.source_id)]
        claim = adapter.create_material_claim(
            estore,
            subject="材料",
            predicate="包含",
            object="相关内容",
            statement=f"材料中包含相关内容（{filename}）",
            passage_ids=passage_ids[:1],
        )
        store.link_capability_claim(
            capability, claim["claim_id"], role="supports", rationale="M5-c 测试夹具（等价闸门写入）"
        )
        return claim

    for filename, (content, evidence_type) in MATERIALS.items():
        add_material(filename, content, evidence_type)

    session = assess_capability(store, estore, capability_id=capability)
    gaps = {
        gap["dimension"]: gap
        for gap in store.list_gaps(capability_id=capability, status="open")
    }
    return {
        "goal_id": GOAL_ID,
        "capability": capability,
        "capability_path": store.get_capability(capability)["path"],
        "other_capability": other_capability,
        "other_capability_path": (
            store.get_capability(other_capability)["path"] if other_capability else None
        ),
        "session": session,
        "gaps": gaps,
    }


def task_payload(gap_id: str, **overrides) -> dict:
    payload = {
        "gap_id": gap_id,
        "title": "写一个 10 条样本的检索评测集",
        "objective": "产出一个 Markdown 评测集（10 条样本与判定标准）",
        "deliverable_type": "markdown",
        "est_minutes": 60,
        "acceptance_type": "artifact_check",
        "acceptance": "提交 Markdown，且包含 10 条样本与判定标准",
        "generated_by_run_id": "m5c_test",
    }
    payload.update(overrides)
    return payload


def create_active_task(store, gap: dict, **overrides) -> str:
    identifier = store.create_task(task_payload(gap["id"], **overrides))
    store.activate_task(identifier)
    return identifier


def deepest_capability_path(prompt: str) -> str:
    """从绑定提示的"目标能力树"里取最深层的能力路径（测试对例默认选叶节点）。

    注意：提示里列出的是**全部 active 能力点**（含领域/分组节点）；M5-c 不限制模型的
    选择（不改 M4-b），而是由 loop 后置条件保证"必须落在任务能力点"。
    """
    tree = prompt.split("目标能力树", 1)[1]
    paths = [line[2:].strip() for line in tree.splitlines() if line.startswith("- ")]
    return max(paths, key=lambda path: (path.count("/"), -len(path)))


def make_binding_proposer(*, path: str | None = None, decline: bool = False):
    """FakeGateway 的 `claim_binding` 响应：从提示中取 claim_id 与能力路径。"""

    def proposer(index: int, system: str, user: str):
        claim_id = re.search(r"clm_[0-9a-f]{6,}", user).group(0)
        if decline:
            return {"proposals": []}
        return {
            "proposals": [
                {
                    "claim_id": claim_id,
                    "capability_path": path or deepest_capability_path(user),
                    "rationale": "提交材料与该能力点直接相关（测试对例）",
                }
            ]
        }

    return proposer
