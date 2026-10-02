"""M1-e：生成能力证据档案（dossier）并**核对**它与数据库、M1-d 留档一致。

用户锁定的五条验收标准，逐条对应到产物：

1. 主张状态可追溯  -> 每条主张一份档案 + 一份并列索引（disputed 与 machine_reviewed 对照）
2. 证据链完整      -> 档案第二节按「原始来源 → 段落摘录 → 抽取 → 复核 → 对抗 → 终态」呈现
3. 缺失证据明确    -> 档案第三节单列，并显式声明"缺失 ≠ 造假"
4. 状态语义准确    -> 档案第四节分别给出 independent_verifier 与 independent_source
5. 可验收产物      -> 档案头部含生成时间/数据范围/脚本；本脚本负责与 DB、artifacts/m1d 核对

核对项（防止档案与事实脱节）：
  · 档案里的 claim 状态、分数与数据库一致
  · 档案里的 verifier_model / verifier_independent 与 claim.metadata 一致
  · 档案里的攻击裁决与 artifacts/m1d/attack_reports.json 一致
  · 档案里的 missing_evidence 与 attack_reports 一致
  · **partial 极性的复核证据必须出现在档案里**（evkg 自带渲染器会漏掉它）

不扩展到 M1-f；也不把这两条主张的结果泛化为系统整体评估可靠。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from growth_os.evidence import adapter, dossier

OUT_DIR = REPO_ROOT / "artifacts" / "m1e"
DB = str(REPO_ROOT / "data" / "growth.db")
M1D = REPO_ROOT / "artifacts" / "m1d"


def main() -> int:
    adapter.configure()
    store = adapter.open_store(DB)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    claims = sorted(store.get_claims(), key=lambda c: c.id)
    if not claims:
        print("库里没有主张，无法生成档案")
        return 1

    print(f"=== 生成 {len(claims)} 份档案 ===")
    records = []
    for claim in claims:
        safe = claim.id.replace("clm_", "")
        output = OUT_DIR / f"dossier-{safe}.md"
        result = dossier.write(store, claim.id, output, db_path=DB)
        records.append({"claim_id": claim.id, "status": claim.status.value,
                        "output": str(output.relative_to(REPO_ROOT)),
                        "confidence": claim.confidence.score,
                        "markdown_chars": len(result["markdown"])})
        print(f"  {claim.id}  status={claim.status.value:<16} score={claim.confidence.score}  "
              f"-> {output.relative_to(REPO_ROOT)}  ({len(result['markdown'])} chars)")

    # 并列索引：把两条主张的状态摆在一起，便于对照
    index_lines = [
        "# 能力证据档案索引（M1-e）",
        "",
        f"- 生成时间：{records and dossier._now()}",
        f"- 数据库：`{Path(DB).relative_to(REPO_ROOT)}`",
        "- 生成脚本：`artifacts/m1e/run_dossier.py`",
        "",
        (
            "> **范围声明**：本索引只覆盖当前库中的主张，**不构成**对系统整体能力评估能力的结论。"
            "库内的归属层尚未建立，项目产物只能证明材料自身内容，不能证明用户个人实现。"
        ),
        "",
        "| 主张 ID | 三元组 | 最终状态 | 置信度 | 档案 |",
        "|---|---|---|---|---|",
    ]
    for claim, record in zip(claims, records):
        index_lines.append(
            f"| `{claim.id}` | {claim.predicate} → {claim.object[:36]} | "
            f"**`{claim.status.value}`** | {claim.confidence.score} | "
            f"[{Path(record['output']).name}]({Path(record['output']).name}) |"
        )
    index_lines += [
        "",
        "## 两条主张的对照要点",
        "",
        (
            "- `disputed` 的那条：证据只能证明**项目存在 RAG 检索模块**，不能证明用户本人实现；"
            "独立复核给出 `partial`，对抗两次裁决 `broken`。缺失证据见其档案第三节。"
        ),
        "- `machine_reviewed` 的那条：内容是**未来规划**，主张本身只陈述「这是计划」，未声称已具备能力，故缺失实践证据不削弱它。",
        "",
        "**不可由本索引推出**：用户是否具备 RAG 能力、系统能否可靠评估任意能力。",
        "",
    ]
    index_path = OUT_DIR / "INDEX.md"
    index_path.write_text("\n".join(index_lines), encoding="utf-8")
    print(f"  索引 -> {index_path.relative_to(REPO_ROOT)}")

    # ---------------- 核对：档案 vs 数据库 vs M1-d 留档 ----------------
    print("\n=== 核对（档案 ↔ 数据库 ↔ artifacts/m1d）===")
    checks: list[tuple[str, bool, str]] = []

    attack_reports = json.loads((M1D / "attack_reports.json").read_text(encoding="utf-8"))
    reports_by_claim: dict[str, list] = {}
    for report in attack_reports:
        reports_by_claim.setdefault(report["target_id"], []).append(report)

    for claim in claims:
        markdown = (OUT_DIR / f"dossier-{claim.id.replace('clm_', '')}.md").read_text(encoding="utf-8")
        tag = claim.id[-8:]

        checks.append((f"[{tag}] 档案含最终状态 {claim.status.value}",
                       f"`{claim.status.value}`" in markdown, ""))
        checks.append((f"[{tag}] 档案含置信度 {claim.confidence.score}",
                       str(claim.confidence.score) in markdown, ""))
        checks.append((f"[{tag}] 档案含 verifier 独立性取值",
                       f"independent_verifier = {claim.metadata.get('verifier_independent')}" in markdown, ""))
        checks.append((f"[{tag}] 档案含提取来源独立性取值",
                       "evidence.independent_source" in markdown, ""))
        checks.append((f"[{tag}] 档案声明『缺失证据不等于造假』",
                       "缺失证据不等于造假" in markdown, ""))
        checks.append((f"[{tag}] 档案含生成时间与数据范围",
                       "生成时间" in markdown and "数据范围" in markdown, ""))
        checks.append((f"[{tag}] 档案声明不成立的结论",
                       "本档案不成立的结论" in markdown, ""))

        # 与 M1-d 留档核对裁决与缺失证据
        for report in reports_by_claim.get(claim.id, []):
            verdict = report["payload"].get("verdict", {})
            name = verdict.get("verdict")
            if name:
                checks.append((f"[{tag}] 档案含裁决 `{name}`", f"`{name}`" in markdown, ""))
            for item in verdict.get("missing_evidence", []) or []:
                checks.append((f"[{tag}] 档案含缺失证据「{item[:26]}…」", item in markdown, ""))

        # partial 极性必须出现（evkg 自带渲染器的漏项）
        raw = adapter.claim_dossier(store, claim.id)
        partials = [e for e in raw["evidence"] if e.get("polarity") == "partial"]
        if partials:
            ok = all(p["reasoning"] in markdown for p in partials if p.get("reasoning"))
            checks.append((f"[{tag}] **partial 复核证据未被漏掉**（{len(partials)} 条）", ok,
                           "evkg render_claim_markdown 会漏掉 partial，本模块必须呈现"))

    # 空跑防护：确认 M1-d 留档确实被读到
    checks.append(("M1-d 攻击留档已读到（非空跑）", len(attack_reports) > 0,
                   f"{len(attack_reports)} 条报告"))

    failures = [c for c in checks if not c[1]]
    for name, passed, note in checks:
        suffix = f"  ({note})" if note and not passed else ""
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}{suffix}")
    print(f"\n核对：{len(checks) - len(failures)}/{len(checks)} 通过")

    summary = {"generated": records, "index": str(index_path.relative_to(REPO_ROOT)),
               "checks_total": len(checks), "checks_failed": len(failures),
               "failures": [c[0] for c in failures]}
    (OUT_DIR / "verification.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print("核对结果已保存 artifacts/m1e/verification.json")

    audit = adapter.audit(DB)
    print(f"QG1: status={audit['status']} violations={audit['total_violations']}")
    store.db.close()
    return 0 if (not failures and audit["status"] == "pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
