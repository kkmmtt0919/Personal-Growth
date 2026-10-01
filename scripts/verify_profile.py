"""M1-a 验证：growth 领域包是否真正生效。

只"能加载"不算通过。本脚本验证四件事：

1. YAML 通过 evkg 的 Profile 校验（schema 合法）
2. source_policy 的覆盖**真的生效**（evkg/policies.py 的覆盖机制被触发）
3. 新增 kind 会被**静默忽略**（这是必须记录的陷阱，不是 bug）
4. prompt 与切分规则按成长场景重写后才生效

用法（在仓库根目录）：
    uv run python -X utf8 scripts/verify_profile.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = REPO_ROOT / "backend" / "growth_os" / "evidence" / "profiles" / "growth_os.yaml"

# 允许脚本在未安装本包时直接运行
sys.path.insert(0, str(REPO_ROOT / "backend"))

from evkg.config import Profile, activate, active, load_profile
from evkg.domain import SourceKind
from evkg.ingest.splitting import split_passages_with_spans
from evkg.policies import assess_source

CHECKS: list[dict] = []


def check(name: str, ok: bool, detail: str) -> None:
    CHECKS.append({"check": name, "ok": bool(ok), "detail": detail})


def main() -> int:
    # --- 0. 文件存在 -------------------------------------------------------
    check("profile 文件存在", PROFILE_PATH.is_file(), str(PROFILE_PATH))
    if not PROFILE_PATH.is_file():
        return _report()

    # --- 1. 加载与 schema 校验 --------------------------------------------
    # 显式传路径，避免受 EVKG_PROFILE 环境变量干扰
    profile: Profile = load_profile(str(PROFILE_PATH))
    check(
        "schema 校验通过且被 pydantic 解析为 Profile",
        isinstance(profile, Profile) and profile.name == "growth_os",
        f"name={profile.name!r}, language={profile.language!r}",
    )

    # --- 2. 激活后 source_policy 覆盖是否生效 -----------------------------
    activate(str(PROFILE_PATH))
    check("activate() 后进程内 active() 指向本包", active().name == "growth_os", active().name)

    folk = assess_source(SourceKind.FOLK)
    check(
        "folk 的 baseline/rationale 被本包覆盖（弱证据=用户自述）",
        folk["baseline_score"] == 0.35 and "自述" in folk["rationale"],
        f"baseline={folk['baseline_score']}, rationale={folk['rationale'][:40]}...",
    )

    primary = assess_source(SourceKind.PRIMARY)
    check(
        "primary 的 rationale 被覆盖为实践产物语义（非原史的『原始记录』）",
        "实践产物" in primary["rationale"],
        f"rationale={primary['rationale'][:40]}...",
    )

    modern = assess_source(SourceKind.MODERN_STUDY)
    check(
        "modern_study 明确标注为『不参与用户能力评级』",
        "不参与" in modern["rationale"],
        f"rationale={modern['rationale'][:40]}...",
    )

    check(
        "6 个内置 kind 全部被覆盖（数量=6）",
        len(profile.source_policy) == 6,
        f"rules={len(profile.source_policy)}",
    )

    # --- 3. 新增 kind 会被静默忽略（记录陷阱） ----------------------------
    trap = Profile.model_validate(
        {
            "name": "trap_probe",
            "source_policy": [{"kind": "repo_artifact", "baseline": 0.99, "rationale": "自定义类型"}],
        }
    )
    from evkg.config import set_active

    set_active(trap)
    still_primary = assess_source(SourceKind.PRIMARY)
    check(
        "自定义 kind 被静默忽略（未污染内置表，也未新增键）",
        len(trap.source_policy) == 1 and still_primary["rationale"] != "自定义类型",
        "Profile 层接受任意 kind 字符串，但 policies._policy_table() 会 ValueError→continue 忽略",
    )
    activate(str(PROFILE_PATH))  # 恢复

    # --- 4. prompt 与切分规则按成长场景重写 -------------------------------
    adv = profile.prompts.adversarial_system
    check(
        "红队 prompt 覆盖 PRD §8 的质疑清单",
        all(k in adv for k in ("用户自述", "调用现成 API", "独立设计", "反向证据", "过时")),
        f"命中 {sum(k in adv for k in ('用户自述', '调用现成 API', '独立设计', '反向证据', '过时'))}/5 个角度",
    )
    check(
        "抽取规则含『严禁升级』约束（计划/了解 ≠ 具备能力）",
        any("严禁升级" in r for r in profile.prompts.extraction_rules),
        f"rules={len(profile.prompts.extraction_rules)} 条",
    )
    check(
        "复核 prompt 覆盖三类常见高估",
        all(k in profile.prompts.verifier_system for k in ("了解", "现成 API", "计划")),
        "含 了解≠掌握 / API≠独立实现 / 计划≠已完成",
    )

    sample = (
        "我最近在学 RAG。\n"
        "上周用 FastAPI 和 ChromaDB 做了一个检索问答项目，代码在 GitHub 上。\n"
        "说实话 rerank 这块我只是看过论文，还没有自己实现过。\n\n"
        "接下来计划学习 Agent Evaluation。"
    )
    chunks = split_passages_with_spans(sample)
    check(
        "按段落切分生效（4 段而非按单换行切碎）",
        len(chunks) == 4,
        f"切出 {len(chunks)} 段：{[c[0][:18] + '…' for c in chunks]}",
    )

    # --- 5. Source.metadata 可承载细粒度证据类型（R2 的静态部分）----------
    from evkg.domain import Source

    src = Source(
        id="src_probe",
        title="探针",
        kind=SourceKind.PRIMARY,
        metadata={"growth_evidence_type": "repo_artifact", "growth_channel": "user_evidence"},
    )
    check(
        "Source.metadata 可携带 growth_evidence_type / growth_channel",
        src.metadata["growth_evidence_type"] == "repo_artifact"
        and src.metadata["growth_channel"] == "user_evidence",
        f"kind={src.kind.value}, metadata={src.metadata}",
    )

    return _report()


def _report() -> int:
    passed = sum(1 for c in CHECKS if c["ok"])
    total = len(CHECKS)
    result = {
        "profile": str(PROFILE_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
        "passed": passed,
        "total": total,
        "status": "pass" if passed == total else "fail",
        "checks": CHECKS,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
