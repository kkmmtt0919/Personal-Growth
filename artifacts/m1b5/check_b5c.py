"""b.5c 端到端实证：在真实材料上走完 inserted → unchanged → updated 三态。

分两部分：
  A. 真实库：把已有的 3 份真实证据重新 ingest 两次，观察三态与 id/段落稳定性
  B. 临时库：拿真实 Java 文件的副本做内容 A→B 改写，验证用户指定的核心性质

不改动真实库的 source 身份（逻辑身份方案保证同一文件 id 不变）。
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE = REPO_ROOT.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

from evkg.ingest.splitting import split_code_passages
from growth_os.evidence import adapter

REAL_FILES = [
    (WORKSPACE / "mytset-rag" / "README.md", "repo_artifact", "user_evidence"),
    (
        WORKSPACE / "mytset-rag" / "src" / "main" / "java" / "com" / "hw" / "service" / "RagService.java",
        "repo_artifact",
        "user_evidence",
    ),
    (WORKSPACE / "evkg" / "README.md", "external_ref", "domain_reference"),
]


def _snapshot(store) -> dict:
    return {
        s.id: {
            "kind": s.kind.value,
            "content_hash": s.content_hash,
            "passages": len(store.get_passages(source_id=s.id)),
        }
        for s in store.get_sources()
    }


def part_a() -> bool:
    print("=== A. 真实库上的三态循环 ===")
    adapter.configure()
    store = adapter.open_store(str(REPO_ROOT / "data" / "growth.db"))
    ok = True

    # 前置状态：这 3 个来源是在 content_hash 字段存在之前落库的，应当还没有它
    before_hashes = {s.id: s.content_hash for s in store.get_sources()}
    missing = [sid for sid, value in before_hashes.items() if value is None]
    print(f"  ingest 前：{len(missing)}/{len(before_hashes)} 个来源尚无 content_hash"
          f"{'（符合预期：该字段晚于它们落库）' if missing else '（已全部具备）'}")

    ids_before = set(_snapshot(store))

    for path, etype, channel in REAL_FILES:
        if path.is_file():
            adapter.ingest_document(path, store=store, evidence_type=etype, channel=channel)
    mid = _snapshot(store)

    written = [sid for sid in missing if mid[sid]["content_hash"] is not None]
    if missing:
        step1_ok = len(written) == len(missing)
        print(f"  [第 1 次重新 ingest] content_hash 首次写入 {len(written)}/{len(missing)}  "
              f"{'OK（写入确实生效，即 updated）' if step1_ok else '!! 写入未生效'}")
    else:
        step1_ok = True
        print("  [第 1 次重新 ingest] 本机已处于稳态，无法再次观测首次写入；"
              "该迁移在字段引入后的首次运行中已观测（那次 output 显示 3 个来源由 None 变为有值）")
    ok &= step1_ok

    # 说明：ingest_document 内部已调用过 save_source，"updated"发生在那一步之内；
    # 下面这次显式 save_source 用于观测"内容未变"这一态。
    second = [(s.id, str(store.save_source(s))) for s in store.get_sources()]
    after = _snapshot(store)
    step2_ok = all(outcome.endswith("unchanged") for _, outcome in second)
    ok &= step2_ok
    print(f"  [第 2 次重新 ingest] 期望 unchanged：{'OK' if step2_ok else '!! 意外'}")
    for sid, outcome in second:
        print(f"    {sid}  {outcome}")

    stable_ids = ids_before == set(after)
    ok &= stable_ids
    print(f"  source 身份稳定: {stable_ids}  （{len(after)} 个，全部保留）")

    no_growth = all(mid[sid]["passages"] == after[sid]["passages"] for sid in after)
    ok &= no_growth
    print(f"  unchanged 时 passage 数不增长: {no_growth}  "
          f"{ {sid: after[sid]['passages'] for sid in after} }")

    all_hashed = all(after[sid]["content_hash"] is not None for sid in after)
    ok &= all_hashed
    print(f"  content_hash 全部已写入: {all_hashed}")
    for sid in after:
        print(f"    {sid}  {str(after[sid]['content_hash'])[:16]}…  passages={after[sid]['passages']}")

    audit = adapter.audit(str(REPO_ROOT / "data" / "growth.db"))
    ok &= audit["status"] == "pass"
    print(f"  QG1: {audit['status']} violations={audit['total_violations']}")
    store.db.close()
    return ok


def part_b() -> bool:
    print("\n=== B. 真实材料上的 内容 A → B 核心性质 ===")
    work = REPO_ROOT / "artifacts" / "m1b5" / "_b5c_scratch"
    if work.exists():
        shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    db = work / "scratch.db"
    adapter.configure()
    store = adapter.open_store(str(db))

    source_file = WORKSPACE / "mytset-rag" / "src" / "main" / "java" / "com" / "hw" / "service" / "RagService.java"
    target = work / "RagService.java"
    shutil.copyfile(source_file, target)
    language = "java"

    def expected_ids() -> set[str]:
        text = target.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
        return {
            p.id
            for p in split_code_passages(text, source_id=sid, path=str(target), language=language)
        }

    # --- A 态 ---
    first = adapter.ingest_document(target, store=store, evidence_type="repo_artifact")
    sid = first.source_id
    hash_a = store.get_source(sid).content_hash
    passages_a = store.passage_ids(sid)
    print(f"  A 态: source_id={sid}  content_hash={str(hash_a)[:16]}…  passages={len(passages_a)}")

    outcome = str(store.save_source(store.get_source(sid)))
    print(f"  同内容重写 -> {outcome}  {'OK' if outcome.endswith('unchanged') else '!! 意外'}")

    # --- B 态：**真正改写内容**（替换方法体，使旧段落真的失效；追加不会） ---
    original = target.read_text(encoding="utf-8")
    marker = "return testCaseMapper.findByKeyword(userInput);"
    assert marker in original, "构造用例失效：待替换的语句不在文件里"
    target.write_text(
        original.replace(marker, "return testCaseMapper.findByKeywordV2(userInput);"),
        encoding="utf-8",
    )
    adapter.ingest_document(target, store=store, evidence_type="repo_artifact")
    hash_b = store.get_source(sid).content_hash
    passages_b = store.passage_ids(sid)
    print(f"  B 态: source_id={sid}  content_hash={str(hash_b)[:16]}…  passages={len(passages_b)}")

    expected_b = expected_ids()
    purged = passages_a - expected_b
    audit = adapter.audit(str(db))
    checks = [
        ("仍然只有一个逻辑 source", store.counts()["sources"] == 1),
        ("下游引用的 source_id 不变", store.get_source(sid) is not None),
        ("content_hash 发生变化", hash_a != hash_b),
        ("新 passage 完整存在（与当前内容重新切分一致）", passages_b == expected_b),
        ("确有旧 passage 被清理（替换语句所在的段落）", len(purged) >= 1),
        ("被清理的旧 passage 已不在库里", store.db.execute(
            "SELECT COUNT(*) FROM passages WHERE id IN ({})".format(",".join("?" for _ in purged)),
            tuple(purged),
        ).fetchone()[0] == 0),
        ("新内容已落库", any(
            "findByKeywordV2" in p.text for p in store.get_passages(source_id=sid))),
        ("库仍然自洽", audit["status"] == "pass"),
    ]
    ok = True
    for name, passed in checks:
        ok &= passed
        print(f"    [{'PASS' if passed else 'FAIL'}] {name}")
    print(f"    （被清理段落 {len(purged)} 条；保留 {len(passages_a) - len(purged)} 条 —— "
          f"未改动部分内容相同、id 相同，本应保留）")
    store.db.close()
    shutil.rmtree(work, ignore_errors=True)
    return ok


def main() -> int:
    a = part_a()
    b = part_b()
    print(f"\n=== b.5c 端到端: {'全部通过' if (a and b) else '有失败'} ===")
    return 0 if (a and b) else 1


if __name__ == "__main__":
    raise SystemExit(main())
