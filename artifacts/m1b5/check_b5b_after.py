"""b.5b 前后对照实证脚本（临时诊断用，不入库）。

用法：uv run python -X utf8 artifacts/m1b5/check_b5b_after.py
"""

from evkg.config import activate

activate("default")

from evkg.domain import Source, SourceKind
from evkg.policies import (
    assess_source,
    preliminary_claim_confidence,
    resolve_source_assessment,
)

print("=== 改动后的行为（与「改动前」逐项对照）===\n")

print("[1] 完全没有来源分级时：")
r = preliminary_claim_confidence(0.9, [])
print(f"    score={r['score']}  source_reliability={r['source_reliability']}  status={r['assessment_status']}")
print(f"    rationale={r['rationale']}\n")

print("[2] 来源行存在但没缓存 assessment：")
s = Source(id="src_code", title="RagService.java", kind=SourceKind.CODE, metadata={})
r = preliminary_claim_confidence(0.95, [resolve_source_assessment(s)])
print(f"    score={r['score']}  status={r['assessment_status']}   （改动前是 0.25）\n")

print("[3] * 危害实例复检：CODE 来源无缓存分级")
resolved = resolve_source_assessment(s)
policy = assess_source(SourceKind.CODE)["baseline_score"]
print(f"    策略表基线={policy}  实际用于加权={resolved['baseline_score']}  差={policy - resolved['baseline_score']:.2f}")
print(f"    origin={resolved['origin']}  <- 如实标出「只用了类型先验」，未逐来源评估\n")

print("[4] 对照：来源记录丢失（完整性错误）")
r = preliminary_claim_confidence(0.99, [resolve_source_assessment(None)])
print(f"    score={r['score']}  status={r['assessment_status']}")
print("    -> 抽取质量 0.99 也拿不到任何分数，未被「未评估」抬成高分\n")

print("[5] 对照：SourceKind.UNKNOWN 的既有低先验（需求要求保持不变）")
u = assess_source(SourceKind.UNKNOWN)
print(f"    baseline={u['baseline_score']}  status={u['status']}  origin={u['origin']}")
print("    -> 仍是一条明确的策略先验，与「未评估」状态可区分\n")

print("[6] 已评估情形数值是否逐位不变：")
ok = True
for kind, expected in [
    (SourceKind.PRIMARY, 0.82),
    (SourceKind.CODE, 0.80),
    (SourceKind.CONTEMPORARY, 0.78),
    (SourceKind.COMPILATION, 0.68),
    (SourceKind.MODERN_STUDY, 0.62),
    (SourceKind.FOLK, 0.35),
    (SourceKind.UNKNOWN, 0.25),
]:
    got = preliminary_claim_confidence(0.9, [assess_source(kind)])["score"]
    same = got == expected
    ok &= same
    print(f"    {kind.value:<14} 期望 {expected}  实际 {got}  {'OK' if same else '!! 变了'}")

print(f"\n=== 已评估数值是否全部不变: {'是' if ok else '否'} ===")
