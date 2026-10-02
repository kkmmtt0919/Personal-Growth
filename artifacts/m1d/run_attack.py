"""M1-d：对能力断言执行攻击（五件套中的前四件 + 审计）。

按用户要求保留三类材料，并显式记录独立性状态：

* **攻击样例** —— 红队生成的最锋利质疑（probes）与裁决（verdicts）
* **复核结果** —— 逐条 claim 的复核结论、担忧点、置信度重算
* **失败记录** —— 模块级错误、批次失败，以及"无法独立复核"的降级状态

范围说明：`damage`（故障注入自测）属 M1-f，本脚本**不跑**，保持小步边界。

独立性：先解析并打印**实际生效**的 provider / 模型名（不是只看环境变量），
再把该状态写入产物 —— 非独立复核的结果不得与独立复核混为一谈。

用法：
    uv run --env-file .env python -X utf8 artifacts/m1d/run_attack.py <db>
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from growth_os.evidence import adapter  # noqa: E402

OUT_DIR = REPO_ROOT / "artifacts" / "m1d"
MODULES = ("deterministic", "verifier", "contradiction", "adversarial", "audit")


def _write(name: str, payload) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / name
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  已保存 {path.relative_to(REPO_ROOT)}  ({path.stat().st_size} bytes)")


async def main() -> int:
    from evkg.attack import get_attack_reports, run_attack
    from evkg.attack.verifier import verifier_gateway
    from evkg.model_gateway import ModelGateway
    from evkg.store import KnowledgeStore

    db = sys.argv[1] if len(sys.argv) > 1 else str(REPO_ROOT / "data" / "growth.db")
    adapter.configure()
    store = KnowledgeStore(db)

    # ---- 独立性解析：看实际生效的配置，而不是环境变量是否被设置 ----
    verify_gateway, independent_flag = verifier_gateway()
    independence = {
        "independent_flag_from_evkg": independent_flag,
        "verifier_provider": verify_gateway._cfg("LLM_PROVIDER", "-"),
        "verifier_model": verify_gateway._cfg("MODEL", "-"),
        "verifier_base_url": verify_gateway._cfg("BASE_URL", "-"),
        "main_provider": ModelGateway()._cfg("LLM_PROVIDER", "-"),
        "main_model": ModelGateway()._cfg("MODEL", "-"),
        "main_base_url": ModelGateway()._cfg("BASE_URL", "-"),
    }
    independence["genuinely_independent"] = bool(
        independent_flag
        and independence["verifier_model"] != independence["main_model"]
        and independence["verifier_base_url"] != independence["main_base_url"]
    )
    # evkg 的 independent 只检查"有没有 overrides"；这里额外核实模型与端点确实不同。
    independence["caveat"] = (
        "evkg 的 verifier_gateway() 返回的布尔值只表示『配置了 overrides』，"
        "并不比对模型是否真的不同；genuinely_independent 是本脚本按模型名+端点另行判定的。"
        "另外实测发现：直接问模型『你是谁』不可靠 —— deepseek-flash 回答 'ChatGPT'。"
        "因此模型身份只以解析后的配置与接口返回为准。"
    )
    print("=== 独立性解析 ===")
    for key, value in independence.items():
        if key != "caveat":
            print(f"  {key}: {value}")
    _write("independence.json", independence)

    print(f"\n=== 运行攻击（{len(MODULES)} 个模块：{'/'.join(MODULES)}；damage 属 M1-f，不跑）===")
    result = await run_attack(db, modules=MODULES, max_probes=10)
    print(f"  summary: {result['summary']}")
    _write("attack_result.json", result)

    # ---- 失败记录：模块级错误 + 明细中的失败项 ----
    failures = {
        "module_errors": {
            name: item for name, item in result["results"].items() if item.get("status") == "error"
        },
        "verifier_details": [],
        "adversarial_verdicts": [],
    }
    verifier_result = result["results"].get("verifier", {})
    for detail in verifier_result.get("details", []):
        failures["verifier_details"].append(detail)
    adversarial = result["results"].get("adversarial", {})
    for item in adversarial.get("results", adversarial.get("details", [])) or []:
        failures["adversarial_verdicts"].append(item)
    _write("failures_and_details.json", failures)

    # ---- 攻击样例：红队质疑与裁决 ----
    reports = get_attack_reports(db, limit=200)
    by_kind: dict[str, list] = {}
    for report in reports:
        by_kind.setdefault(report["kind"], []).append(report)
    print("\n=== 攻击报告（按 kind）===")
    for kind, items in sorted(by_kind.items()):
        print(f"  {kind}: {len(items)} 条")
    _write("attack_reports.json", reports)

    # ---- 攻击后的 claim 状态 ----
    claims = store.get_claims()
    print(f"\n=== 攻击后的主张（{len(claims)} 条）===")
    claims_dump = []
    for claim in claims:
        score = claim.confidence.score
        metadata = claim.metadata or {}
        row = {
            "id": claim.id,
            "statement": claim.statement,
            "predicate": claim.predicate,
            "status": claim.status.value,
            "score": score,
            "source_reliability": claim.confidence.source_reliability,
            "assessment_status": claim.confidence.assessment_status,
            "rationale": claim.confidence.rationale,
            "review_state": metadata.get("review_state"),
            "verifier_model": metadata.get("verifier_model"),
            "verifier_independent": metadata.get("verifier_independent"),
            "assessment_status_meta": metadata.get("assessment_status"),
        }
        claims_dump.append(row)
        print(f"\n  [{claim.id}] {claim.predicate} | {claim.object[:44]}")
        print(f"    状态={row['status']}  分数={score}  来源可靠性={row['source_reliability']}")
        print(f"    review_state={row['review_state']}  verifier={row['verifier_model']}  "
              f"verifier_independent={row['verifier_independent']}")
        print(f"    理由: {(row['rationale'] or '')[:150]}")
    _write("claims_after_attack.json", claims_dump)

    # ---- 冲突与候选 ----
    conflicts = [dict(zip(("id", "payload"), (r[0], json.loads(r[1]))))
                 for r in store.db.execute("SELECT id, payload FROM conflicts").fetchall()]
    candidates = [dict(zip(("id", "status", "dimension", "payload"),
                           (r[0], r[1], r[2], json.loads(r[3]))))
                  for r in store.db.execute(
                      "SELECT id, status, dimension, payload FROM conflict_candidates").fetchall()]
    print(f"\n冲突: {len(conflicts)}   冲突候选: {len(candidates)}")
    _write("conflicts.json", {"conflicts": conflicts, "conflict_candidates": candidates})

    counts = store.counts()
    print(f"\n库计数: {json.dumps({k: v for k, v in counts.items() if k != 'audit_log'}, ensure_ascii=False)}")
    _write("counts.json", {k: v for k, v in counts.items() if k != "audit_log"})

    audit = adapter.audit(db)
    print(f"QG1: status={audit['status']} violations={audit['total_violations']}")
    store.db.close()
    return 0 if audit["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
