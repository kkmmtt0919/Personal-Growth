"""受控本地 Demo：零网络调用，复用评估与提交闭环，独立于用户数据库。"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .agent import FakeGateway
from .assessment import BINDING_TASK, ClaimBinder, TaskLoop, assess_capability
from .evidence import adapter
from .memory import MemoryProjection, MemoryService
from .store import GrowthStore

DEMO_DIRECTORY = Path(__file__).resolve().parents[2] / "data" / "demo"


async def seed_demo(directory: Path = DEMO_DIRECTORY, *, include_return: bool = False) -> dict:
    directory = directory.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    database = directory / "demo.db"
    if database.exists():
        raise ValueError(f"Demo 数据库已存在，保留原数据：{database}；可直接启动服务")
    store = GrowthStore(str(database))
    evidence = adapter.open_store(database)
    try:
        store.upsert_user("local", "受控 Demo 用户")
        store.save_goal({
            "id": "goal_demo", "user_id": "local", "title": "成为 AI Agent 工程师",
            "direction": "AI 应用", "purpose": "求职", "horizon": "6 个月",
            "measurable_result": "完成可演示的 RAG 项目", "status": "confirmed",
            "source_quote": "受控 Demo：成为 AI Agent 工程师",
        })
        path = "AI Agent/工具与执行/RAG 系统搭建与调优"
        capability = store.upsert_capability({
            "goal_id": "goal_demo", "path": path, "name": "RAG 系统搭建与调优",
            "depth": 3, "target_level": 4,
        })

        def propose(index: int, system: str, user: str) -> dict:
            claim = re.search(r"clm_[0-9a-f]{6,}", user)
            if claim is None:
                raise ValueError("绑定提示缺少材料主张")
            return {"proposals": [{"claim_id": claim.group(0), "capability_path": path,
                                   "rationale": "受控 Demo：材料直接对应 RAG 实践"}]}

        gateway = FakeGateway(responses={BINDING_TASK: propose})
        binder = ClaimBinder(store=store, evidence_store=evidence, gateway=gateway,
                             goal_id="goal_demo")
        for filename, text, kind in [
            ("notes.md", "# 受控 Demo 笔记\n\nRAG 检索流程：切分、向量化、召回、重排。\n", "uploaded_doc"),
            ("project.md", "# 受控 Demo 项目\n\n实现了最小检索服务与命令行入口。\n", "repo_artifact"),
        ]:
            material = directory / filename
            material.write_text(text, encoding="utf-8")
            ingested = adapter.ingest_document(
                material, store=evidence, evidence_type=kind, attribution="user_declared",
                extra_metadata={"growth_constructed": True,
                                "growth_constructed_note": "受控 Demo，不代表真实用户成果"},
            )
            passages = evidence.get_passages(source_id=ingested.source_id)
            claim = adapter.create_material_claim(
                evidence, subject="材料", predicate="包含", object="RAG 内容",
                statement=f"受控材料包含 RAG 内容（{filename}）", passage_ids=[passages[0].id],
            )
            result = await binder.propose([claim["claim_id"]])
            if not result["accepted"]:
                raise ValueError("Demo 初始证据绑定被拒")
        assess_capability(store, evidence, capability_id=capability)
        return_context = None
        if include_return:
            MemoryService(store).remember(
                layer="profile", key="learning_style",
                value={"text": "喜欢代码实践，先看架构再看源码"},
                source_kind="user_statement", source_id="statement_demo_constructed_preference",
            )
            baseline = MemoryProjection(store).project()["snapshots"][0]["id"]
        gap = next(g for g in store.list_gaps(capability_id=capability, status="open")
                   if g["dimension"] == "practice")
        task = store.create_task({
            "gap_id": gap["id"], "title": "实现 Agent Evaluation 评测实验",
            "objective": "产出包含十条 RAG 检索样本与判定标准的评测报告",
            "deliverable_type": "markdown", "est_minutes": 60,
            "acceptance_type": "artifact_check", "acceptance": "提交十条样本与判定标准",
            "generated_by_run_id": "m8_constructed_demo",
        })
        store.activate_task(task)
        submission = directory / "evaluation.md"
        submission.write_text(
            "# 受控 Demo：Agent Evaluation\n\n不代表真实用户成果。\n\n"
            + "\n".join(f"{i}. 检索样本 {i}：回答应引用对应来源；无匹配时报告不足。"
                        for i in range(1, 11)), encoding="utf-8",
        )
        loop = TaskLoop(store=store, evidence_store=evidence, gateway=gateway,
                        submission_dir=directory / "submissions", report_directory=directory / "reports")
        outcome = await loop.complete_task(task, artifact_path=submission, note="受控 Demo")
        attribution = outcome["attribution"]
        if (attribution["before"]["practice"]["level"],
                attribution["after"]["practice"]["level"]) != (3, 4):
            raise ValueError("Demo 未通过实践 3 → 4 验证")
        if not all(attribution["guard"].values()):
            raise ValueError("Demo 归因守卫未通过")
        if include_return:
            MemoryProjection(store).project()
            current = next(row["id"] for row in store.list_snapshots() if row["id"] != baseline)
            return_context = {
                "baseline_snapshot_id": baseline, "current_snapshot_id": current,
                "returned_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
                "simulated_return": True, "seed_process_id": os.getpid(),
            }
        manifest = {"constructed": True, "note": "受控 Demo，不代表真实用户成果",
                    "goal_id": "goal_demo", "capability_id": capability,
                    "task_id": task, "loop_reports": {task: attribution}}
        if return_context:
            manifest["return_context"] = return_context
        (directory / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        return manifest
    finally:
        evidence.db.close()
        store.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="创建独立的受控 Demo（零模型/网络调用）")
    parser.add_argument("--directory", type=Path, default=DEMO_DIRECTORY)
    parser.add_argument("--with-return", action="store_true", help="加入受控长期偏好和隔天返回快照")
    args = parser.parse_args()
    manifest = asyncio.run(seed_demo(args.directory, include_return=args.with_return))
    print(json.dumps({k: v for k, v in manifest.items() if k != "loop_reports"},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
