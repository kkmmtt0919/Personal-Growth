"""D1 实测：evkg 的领域包（profile）是进程级全局，还是实例级状态？

问题（用户 M1-g 指定，必须实测，不得推定）：
  1. profile 是模块级、进程级，还是实例级状态？
  2. 两个不同配置的实例能否在同一进程中独立运行？
  3. 初始化顺序是否会改变另一个实例的行为？
  4. 测试是否存在顺序依赖？（经验性检查在报告里，用正序/逆序两轮 pytest 佐证）
  5. 若确实是共享全局状态，能否用现有公开 API 隔离，还是必须改上游？

方法：两个可观察行为不同的探针领域包（切分边界、代码语言表不同）× 两个独立
KnowledgeStore（两个独立 DB）。所有数据都落在 artifacts/m1g/tmp，绝不触碰
data/growth.db（脚本首尾各记一次 SHA-256 佐证）。
"""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import shutil
from pathlib import Path

import evkg.config as cfg
from evkg.config import Profile, activate, active, set_active
from evkg.ingest import ingest_path
from evkg.store import KnowledgeStore

HERE = Path(__file__).resolve().parent
TMP = HERE / "tmp"
PROFILE_A = HERE / "profiles" / "probe_alpha.yaml"
PROFILE_B = HERE / "profiles" / "probe_beta.yaml"
REAL_DB = Path("D:/projects/Personal Growth/data/growth.db")
OUT = HERE / "d1_profile_isolation.json"

TEXT = "alpha one\nbeta two\n\ngamma three\ndelta four\n"
TEXT_NAME = "probe_text.txt"


def sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def split_signature(store: KnowledgeStore, source_id: str) -> dict:
    passages = store.get_passages(source_id=source_id)
    return {
        "count": len(passages),
        "texts": [item.text for item in passages],
        "locators": [item.locator for item in passages],
    }


def build_case() -> dict:
    """准备干净的工作目录与两个 store，并记录纯静态事实。"""
    if TMP.exists():
        shutil.rmtree(TMP)
    TMP.mkdir(parents=True)
    (TMP / TEXT_NAME).write_text(TEXT, encoding="utf-8")
    (TMP / "probe.a1").write_text("def one():\n    return 1\n", encoding="utf-8")
    (TMP / "probe.b1").write_text("def two():\n    return 2\n", encoding="utf-8")

    # 两个 store 在任何 activate() 之前创建：证明 store 构造不读取 profile。
    store_a = KnowledgeStore(str(TMP / "store_a.db"))
    store_b = KnowledgeStore(str(TMP / "store_b.db"))

    static = {
        "active_before_any_activate_is_default": active().name,
        "_ACTIVE_is_module_attribute": isinstance(cfg.__dict__.get("_ACTIVE"), Profile),
        "KnowledgeStore_init_params": list(inspect.signature(KnowledgeStore.__init__).parameters),
        "store_has_profile_attribute": hasattr(store_a, "profile"),
        "ingest_path_params": list(inspect.signature(ingest_path).parameters),
        "profile_obj_identity_switches_with_activate": None,
        "profile_call_sites": [
            "config.code_language_for",
            "ingest.splitting._boundary_pattern",
            "ingest.splitting.split_code_passages",
            "ingest.pipeline._annotate",
            "store._enrich_event_time",
            "policies._policy_table",
            "extract._prompt / extract_corpus",
            "entity_resolution / text_normalization / attack.* / web",
        ],
    }
    p1 = activate(str(PROFILE_A))
    obj_a = active()
    p2 = activate(str(PROFILE_B))
    obj_b = active()
    static["profile_obj_identity_switches_with_activate"] = {
        "activations_return_own_objects": (p1.name, p2.name),
        "active_is_latest_object": obj_b is p2 and obj_b is not obj_a,
    }
    return {"store_a": store_a, "store_b": store_b, "static": static}


def part1_sequential_interleaving(case: dict) -> dict:
    """两个实例交错使用：storeA 的行为是否被『另一实例的初始化』改变。"""
    store_a, store_b = case["store_a"], case["store_b"]
    text_path = TMP / TEXT_NAME
    logs: dict = {}

    activate(str(PROFILE_A))
    src_a1 = ingest_path(text_path, store=store_a, task_id="d1_a1")
    sig_a1 = split_signature(store_a, src_a1.id)

    activate(str(PROFILE_B))
    src_b1 = ingest_path(text_path, store=store_b, task_id="d1_b1")
    sig_b1 = split_signature(store_b, src_b1.id)

    # 关键步：不重新 activate(A)，直接向 storeA 再次入库同一份文件。
    src_a2 = ingest_path(text_path, store=store_a, task_id="d1_a2")
    sig_a2 = split_signature(store_a, src_a2.id)

    # 重新 activate(A) 后再入库：行为是否恢复。
    activate(str(PROFILE_A))
    src_a3 = ingest_path(text_path, store=store_a, task_id="d1_a3")
    sig_a3 = split_signature(store_a, src_a3.id)

    logs["a_under_A_first"] = sig_a1
    logs["b_under_B"] = sig_b1
    logs["a_under_B_without_reactivate"] = sig_a2
    logs["a_after_reactivate_A"] = sig_a3
    logs["source_ids_identical"] = len({src_a1.id, src_a2.id, src_a3.id, src_b1.id}) == 1
    logs["contaminated"] = sig_a2["count"] == sig_b1["count"] and sig_a2["count"] != sig_a1["count"]
    logs["restored_by_reactivation"] = sig_a3["count"] == sig_a1["count"]
    return logs


def part2_init_order_and_reads(case: dict) -> dict:
    """初始化顺序：store 的创建顺序不重要，最后一次 activate() 才决定行为；
    已写入的数据不受后续 activate() 影响（污染发生在写入时，不在读取时）。"""
    store_a = case["store_a"]
    text_path = TMP / TEXT_NAME
    logs: dict = {}

    activate(str(PROFILE_A))
    src = ingest_path(text_path, store=store_a, task_id="d1_order_1")
    before = split_signature(store_a, src.id)
    activate(str(PROFILE_B))
    after_switch_read = split_signature(store_a, src.id)
    logs["written_under_A_read_under_B_unchanged"] = before == after_switch_read
    logs["read_is_profile_independent"] = before == after_switch_read

    # 新建 store 的顺序不改变结论：谁最后被 activate，谁决定下一次写入。
    store_c = KnowledgeStore(str(TMP / "store_c.db"))
    activate(str(PROFILE_B))
    src_c = ingest_path(text_path, store=store_c, task_id="d1_order_2")
    logs["store_created_after_B_uses_B"] = split_signature(store_c, src_c.id)["count"] == 2
    return logs


async def part3_concurrent_interleaving(case: dict) -> dict:
    """并发（asyncio）下，两个任务的 activate 互相覆盖 —— 用事件强制交错顺序，
    不依赖调度运气。"""
    store_a, store_b = case["store_a"], case["store_b"]
    text_path = TMP / TEXT_NAME
    a_started = asyncio.Event()
    b_done = asyncio.Event()
    logs: dict = {}

    async def worker_a() -> dict:
        activate(str(PROFILE_A))
        a_started.set()
        await b_done.wait()  # 其他任务在两者之间 activate 了 B
        src = ingest_path(text_path, store=store_a, task_id="d1_async_a")
        return split_signature(store_a, src.id)

    async def worker_b() -> dict:
        await a_started.wait()
        activate(str(PROFILE_B))
        src = ingest_path(text_path, store=store_b, task_id="d1_async_b")
        sig = split_signature(store_b, src.id)
        b_done.set()
        return sig

    sig_a, sig_b = await asyncio.gather(worker_a(), worker_b())
    logs["task_a_expected_A_rules"] = 4
    logs["task_a_actual_count"] = sig_a["count"]
    logs["task_b_actual_count"] = sig_b["count"]
    logs["cross_task_contamination"] = sig_a["count"] == 2  # A 的任务用了 B 的规则
    return logs


def part4_isolation_via_public_api(case: dict) -> dict:
    """能否用现有公开 API 隔离？"""
    store_a = case["store_a"]
    text_path = TMP / TEXT_NAME
    profile_a = cfg.load_profile(str(PROFILE_A))
    logs: dict = {}

    # (1) 给实例挂属性没有任何作用：函数不读实例状态。
    store_a.profile = profile_a  # type: ignore[attr-defined]
    activate(str(PROFILE_B))
    src = ingest_path(text_path, store=store_a, task_id="d1_attr")
    logs["instance_attribute_ignored"] = split_signature(store_a, src.id)["count"] == 2

    # (2) 每次调用前重新 activate 并 try/finally 复原：顺序执行可行。
    try:
        activate(str(PROFILE_A))
        src = ingest_path(text_path, store=store_a, task_id="d1_guard")
        logs["per_call_reactivation_works_sequentially"] = split_signature(store_a, src.id)["count"] == 4
    finally:
        set_active(Profile())

    # (3) 是否有任何公开入口接受 profile 参数（避免全局）？
    logs["ingest_path_accepts_profile"] = "profile" in inspect.signature(ingest_path).parameters
    logs["ingest_file_accepts_profile"] = "profile" in inspect.signature(
        __import__("evkg.ingest.connectors", fromlist=["ingest_file"]).ingest_file
    ).parameters
    logs["store_constructor_accepts_profile"] = "profile" in inspect.signature(KnowledgeStore.__init__).parameters
    logs["verdict"] = (
        "顺序执行：公开 API（每次调用前 activate + try/finally）可强制隔离；"
        "并发执行：无任何公开 API 可把 profile 绑定到 store 或调用，必须改上游"
    )
    return logs


def part5_adapter_footgun() -> dict:
    """全局 profile 在 Growth OS 自身 API 面上的后果：适配层不强制 configure()。

    open_store() 会 configure()，但 ingest_document() 接受调用方自建的 store；
    若调用方绕过 open_store，入库会静默使用 evkg 内置 default 领域包（切分与
    评级理由都不同），且没有任何报错。
    """
    import sys

    sys.path.insert(0, str(Path("D:/projects/Personal Growth/backend")))
    from growth_os.evidence import adapter

    TMP.mkdir(parents=True, exist_ok=True)
    note = TMP / "footgun_note.md"
    note.write_text("# 能力笔记\n熟悉 Python\n熟悉 RAG 检索\n\n另一段\n只此一句\n", encoding="utf-8")

    def ingest_with(db_name: str, do_configure: bool) -> dict:
        store = KnowledgeStore(str(TMP / db_name))
        if do_configure:
            adapter.configure()
        else:
            set_active(Profile())  # 模拟"从未 configure"，等价于进程默认
        result = adapter.ingest_document(note, store=store, evidence_type="uploaded_doc")
        meta = adapter.source_metadata(store, result.source_id)
        assessment = meta.get("assessment", {})
        store.db.close()
        return {
            "passage_count": result.passage_count,
            "baseline": assessment.get("baseline_score"),
            "rationale": assessment.get("rationale"),
            "assessment_origin": assessment.get("origin"),
        }

    without = ingest_with("footgun_plain.db", do_configure=False)
    with_configure = ingest_with("footgun_configured.db", do_configure=True)
    return {
        "without_configure": without,
        "with_configure": with_configure,
        "silently_misconfigured": without != with_configure,
        "verdict": (
            "不 configure 时按 evkg 内置 default 领域包入库（切分与理由均不同），"
            "全程无报错 —— 保护依赖调用约定而非结构"
            if without != with_configure
            else "两条路径无差异（需重新设计探针）"
        ),
    }


def main() -> dict:
    real_before = sha256_file(REAL_DB)
    case = build_case()
    report = {
        "probe": "D1 evkg process-global profile isolation",
        "env": {
            "evkg_module": cfg.__file__,
            "profile_a": str(PROFILE_A),
            "profile_b": str(PROFILE_B),
            "text_fixture": TEXT,
        },
        "part0_static_scope": case["static"],
        "part1_sequential_interleaving": part1_sequential_interleaving(case),
        "part2_init_order_and_reads": part2_init_order_and_reads(case),
        "part3_concurrent_interleaving": asyncio.run(part3_concurrent_interleaving(case)),
        "part4_isolation_via_public_api": part4_isolation_via_public_api(case),
        "part5_adapter_footgun": part5_adapter_footgun(),
        "real_db_sha256_before": real_before,
        "real_db_sha256_after": None,
        "real_db_untouched": None,
    }
    report["real_db_sha256_after"] = sha256_file(REAL_DB)
    report["real_db_untouched"] = report["real_db_sha256_before"] == report["real_db_sha256_after"]
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


if __name__ == "__main__":
    main()
