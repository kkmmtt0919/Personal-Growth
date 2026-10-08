"""M4-d：能力解释报告（"为什么是这个星级"）—— **只读**，从已存储评定行 + 证据链派生。

结构（用户 2026-10-03 冻结）：

```text
assessment report
├── capability
├── dimensions        （understanding / practice：level / status / rationale / why_not_higher）
├── supports          （claim 三元组 + 绑定理由 + 逐字引文 + 来源）
├── gaps              （只来自 rubric.gaps；"为什么不是更高"不得另造推断）
├── reverse evidence  （attack 裁决与理由 + refutes 证据行 + 封顶值）
├── excluded          （broken / 准入未通过 / 不可入桶 —— 及原因）
└── rule_version      （可复算声明）
```

三条呈现纪律（沿用 `evidence/dossier.py`）：

* **不把模型判断写成事实**：等级由确定性规则从已绑定证据算出，报告只呈现依据；
* **缺失 ≠ 低能力**：`insufficient_evidence` 只说明"现有材料不足以支持等级"；
* **不外推**：报告不包含对用户本人的推断，也不构成系统整体可靠性的结论。

**不读分级分数**（D6）：报告只复制规则引擎产出的等级与依据，不携带任何模型分值。
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from ..evidence import adapter
from ..store import ASSESSMENT_DIMENSIONS
from .rules import INSUFFICIENT, RATED, RULES_CONTRACT_VERSION

REPORT_LIMITATIONS = (
    "不能由“项目存在”推出“用户个人实现”：材料口径证据只证明材料内容（M3 硬规则）。",
    "缺失证据不等于没做过：insufficient_evidence 只说明现有材料不足以支持等级。",
    "等级由确定性规则从已绑定证据算出、可复算；报告不包含任何模型分值。",
    "报告不构成对系统整体评估可靠性的结论。",
)


def _attack_details(entry: dict) -> list[dict]:
    details: list[dict] = []
    for attack in entry.get("attacks") or []:
        verdict = attack.get("verdict") or {}
        probe = attack.get("probe") or {}
        details.append(
            {
                "angle": probe.get("angle"),
                "question": probe.get("question"),
                "verdict": verdict.get("verdict") or attack.get("verdict"),
                "reasoning": verdict.get("reasoning"),
                "missing_evidence": list(verdict.get("missing_evidence") or []),
            }
        )
    return details


def _refuting_rows(entry: dict) -> list[dict]:
    return [
        {
            "passage_id": link.get("passage_id"),
            "quote": link.get("quote"),
            "reasoning": link.get("reasoning"),
        }
        for link in entry.get("evidence") or []
        if str(link.get("polarity")) == "refutes"
    ]


def _support_detail(claim_id: str, overview: dict, links_by_claim: dict) -> dict:
    entry = overview.get(claim_id)
    if entry is None:
        return {"claim_id": claim_id, "present": False, "reason": "claim 不在证据库中（引用失效）"}
    claim = entry["claim"]
    quotes = [
        {
            "passage_id": link.get("passage_id"),
            "quote": link.get("quote"),
            "quote_verbatim": bool(link.get("quote"))
            and str(link.get("quote")) in str(link.get("passage_text") or ""),
            "source_id": (link.get("source") or {}).get("id"),
            "source_title": (link.get("source") or {}).get("title"),
        }
        for link in entry.get("evidence") or []
        if str(link.get("polarity")) == "supports"
    ]
    binding = links_by_claim.get(claim_id) or {}
    return {
        "claim_id": claim_id,
        "present": True,
        "subject": claim.get("subject"),
        "predicate": claim.get("predicate"),
        "object": claim.get("object"),
        "statement": claim.get("statement"),
        "binding_rationale": binding.get("rationale"),
        "quotes": quotes,
    }


def build_report(store, evidence_store, *, capability_id: str, generated_by: str | None = None) -> dict:
    """装配能力解释报告（只读；调用方负责写文件与销毁临时库）。"""
    capability = store.get_capability(capability_id)
    if capability is None:
        raise KeyError(f"未知能力点: {capability_id}")
    overview = {
        entry["claim"]["id"]: entry for entry in adapter.claims_overview(evidence_store)
    }
    links_by_claim = {
        link["claim_id"]: link
        for link in store.list_capability_claims(capability_id=capability_id)
    }

    dimensions: dict[str, dict] = {}
    supports: list[dict] = []
    gaps: list[dict] = []
    reverse_evidence: list[dict] = []
    excluded: dict[str, dict] = {}
    rule_version = RULES_CONTRACT_VERSION

    for dimension in ASSESSMENT_DIMENSIONS:
        row = store.latest_assessment(capability_id, dimension)
        rubric = json.loads(row["rubric_json"]) if row and row.get("rubric_json") else {}
        if rubric.get("contract"):
            rule_version = rubric["contract"]
        dimensions[dimension] = {
            "assessment_id": row["id"] if row else None,
            "status": row["status"] if row else "unassessed",
            "level": row["level"] if row else None,
            "base_level": rubric.get("base_level"),
            "rationale": row["rationale"] if row else "尚无评定结果",
            "why_not_higher": list(rubric.get("gaps") or []),
            "supports": list(rubric.get("supports") or []),
            "reverse_evidence": list(rubric.get("reverse_evidence") or []),
            "excluded": list(rubric.get("excluded") or []),
        }
        for support in rubric.get("supports") or []:
            detail = _support_detail(support["claim_id"], overview, links_by_claim)
            detail["dimension"] = dimension
            detail["cap"] = support.get("cap")
            detail["signals"] = support.get("signals")
            detail["evidence_types"] = support.get("evidence_types")
            supports.append(detail)
        for gap in rubric.get("gaps") or []:
            gaps.append({"dimension": dimension, "text": gap})
        for item in rubric.get("reverse_evidence") or []:
            entry = overview.get(item["claim_id"]) or {}
            reverse_evidence.append(
                {
                    "dimension": dimension,
                    "claim_id": item["claim_id"],
                    "cap": item.get("cap"),
                    "attacks": _attack_details(entry) if entry else [],
                    "refuting_evidence": _refuting_rows(entry) if entry else [],
                }
            )
        for item in rubric.get("excluded") or []:
            entry = overview.get(item["claim_id"]) or {}
            record = excluded.setdefault(
                item["claim_id"],
                {
                    "claim_id": item["claim_id"],
                    "reason": item.get("reason"),
                    "dimensions": [],
                    "attacks": _attack_details(entry) if entry else [],
                },
            )
            if dimension not in record["dimensions"]:
                record["dimensions"].append(dimension)

    # M4-e 收紧（用户 2026-10-03 冻结的编排顺序：report 先于 apply_assessment_levels）：
    # 当前视图必须从评定行**重算**，而不是读回填缓存列 —— 否则报告会写进回填前的旧值。
    derived = store.expected_assessment_levels(capability_id)
    return {
        "artifact": "m4d-assessment-report",
        "capability": {
            "id": capability_id,
            "goal_id": capability["goal_id"],
            "path": capability["path"],
            "depth": capability["depth"],
            "target_level": capability["target_level"],
            "status": capability["status"],
            "current_level_status": derived["status"],
            "current_level_understanding": derived["understanding"],
            "current_level_practice": derived["practice"],
        },
        "dimensions": dimensions,
        "supports": supports,
        "gaps": gaps,
        "reverse_evidence": reverse_evidence,
        "attack_reviews": [
            {"claim_id": claim_id, "statement": (overview[claim_id].get("claim") or {}).get("statement"),
             "attacks": _attack_details(overview[claim_id])}
            for claim_id in links_by_claim if claim_id in overview and overview[claim_id].get("attacks")
        ],
        "excluded": list(excluded.values()),
        "rule_version": rule_version,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "generated_by": generated_by or "growth_os.assessment.report",
        "limitations": list(REPORT_LIMITATIONS),
        "read_only": True,
    }


def _render_dimension(report: dict, dimension: str) -> list[str]:
    label = "理解" if dimension == "understanding" else "实践"
    body = report["dimensions"][dimension]
    level = body["level"]
    if body["status"] == RATED and level is not None:
        head = f"### {label}：⭐ ×{level}（`rated`）"
    else:
        head = f"### {label}：证据不足（`{body['status'] if body['status'] != 'unassessed' else INSUFFICIENT}`）"
    lines = [head, f"- 评定依据：{body['rationale']}"]
    if body.get("base_level") is not None:
        lines.append(f"- 证据集合基线：{body['base_level']}（维度聚合，可由证据链复算）")
    if body["why_not_higher"]:
        lines.append("- 为什么不是更高（只来自规则引擎的缺口记录）：")
        lines.extend(f"  - {text}" for text in body["why_not_higher"])
    return lines


def render_report(report: dict) -> str:
    """渲染 Markdown（自建渲染器；不使用 evkg `render_claim_markdown`，决定 C2）。"""
    capability = report["capability"]
    out: list[str] = [f"# 能力评估报告：{capability['path']}", ""]

    out.append("## 生成信息")
    out.append(f"- **生成时间**：{report['generated_at']}")
    out.append(f"- **生成者**：`{report['generated_by']}`")
    out.append(
        f"- **能力点**：`{capability['id']}`｜目标等级 {capability['target_level']}"
        f"｜评估状态 `{capability['current_level_status']}`"
    )
    out.append("")

    out.append("## 一、两维度评定")
    for dimension in ("understanding", "practice"):
        out.extend(_render_dimension(report, dimension))
        out.append("")

    out.append("## 二、支持证据（逐字引用）")
    if not report["supports"]:
        out.append("（没有进入评级的支持证据）")
    for support in report["supports"]:
        header = f"### `{support['claim_id']}` → {support.get('dimension')}"
        if support.get("cap") is not None:
            header += f"｜反向封顶 ≤{support['cap']}"
        out.append(header)
        if not support.get("present"):
            out.append(f"- **引用失效**：{support.get('reason')}")
            continue
        out.append(
            f"- 主张：{support.get('subject')} —[{support.get('predicate')}]→ {support.get('object')}"
        )
        out.append(f"- 陈述：{support.get('statement')}")
        if support.get("binding_rationale"):
            out.append(f"- 绑定理由：{support['binding_rationale']}")
        for quote in support.get("quotes") or []:
            out.append(
                f"- 引文（`{quote['passage_id']}`，来源 {quote.get('source_title')}，"
                f"逐字={quote.get('quote_verbatim')}）："
            )
            for line in str(quote.get("quote") or "").splitlines()[:4]:
                out.append(f"  > {line}")
    out.append("")

    out.append("## 三、不足（来自规则引擎的缺口记录）")
    if not report["gaps"]:
        out.append("（规则引擎未记录缺口）")
    for gap in report["gaps"]:
        out.append(f"- [{gap['dimension']}] {gap['text']}")
    out.append("")

    out.append("## 四、反向证据（攻击裁决 / refutes 证据行）")
    if not report["reverse_evidence"]:
        out.append("（本能力点没有被反向证据封顶的主张）")
    for item in report["reverse_evidence"]:
        out.append(f"### `{item['claim_id']}`（{item['dimension']} 侧封顶 ≤{item['cap']}）")
        for attack in item.get("attacks") or []:
            out.append(f"- 攻击裁决 `{attack.get('verdict')}`：{attack.get('reasoning')}")
            if attack.get("missing_evidence"):
                out.append(f"  - 未确认项：{'；'.join(attack['missing_evidence'])}")
        for row in item.get("refuting_evidence") or []:
            out.append(f"- 反驳证据（`{row.get('passage_id')}`）：{row.get('reasoning')}")
    out.append("")

    out.append("## 五、已排除的证据")
    if not report["excluded"]:
        out.append("（没有被排除的已绑定主张）")
    for item in report["excluded"]:
        dimensions = "/".join(item.get("dimensions") or [])
        out.append(f"- `{item['claim_id']}`（{dimensions}）：{item.get('reason')}")
        for attack in item.get("attacks") or []:
            if attack.get("verdict") == "broken":
                out.append(f"  - 攻击裁决 `broken`：{attack.get('reasoning')}")
    out.append("")

    out.append("## 六、规则版本与复算")
    out.append(f"- 规则版本：`{report['rule_version']}`")
    out.append("- 等级由已绑定证据（`g_capability_claims`）经确定性规则算出，可用同一版本复算。")
    out.append("")

    out.append("## 七、本报告不能成立的结论")
    for text in report["limitations"]:
        out.append(f"- {text}")
    out.append("")
    return "\n".join(out)


def write_report(report: dict, *, directory: str | Path, stem: str) -> dict:
    """写出 JSON + Markdown 双份（用户 2026-10-03 冻结的产物形态）。"""
    target = Path(directory)
    target.mkdir(parents=True, exist_ok=True)
    json_path = target / f"{stem}.json"
    markdown_path = target / f"{stem}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(render_report(report), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(markdown_path)}
