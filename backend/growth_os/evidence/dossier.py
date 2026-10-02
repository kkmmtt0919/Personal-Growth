"""Growth OS 证据档案（dossier）—— 让人能读懂"这条能力结论是怎么来的"。

## 与 evkg 自带渲染器的分工

evkg 提供**结构化**的 `claim_dossier`（证据行、攻击史、处理轨迹），本模块负责把它
渲染成面向产品语义的档案。之所以不复用 evkg 的 `render_claim_markdown`：

1. **它会漏掉 `partial` 极性的证据。** 该渲染器只输出 `supports` 与 `refutes` 两个列表，
   而本库里被推翻的那条主张恰恰是 `partial`（独立复核的结论）。漏掉它，等于把
   "复核认为只有部分支持" 从档案里抹掉 —— 而那是关于该主张最重要的一条证据。（已作为
   上游问题记录，见 `.project-to-act/docs/DECISIONS.md`）
2. **它缺少呈现所需的领域语义与元信息**：生成时间、数据范围、两个易混的"独立"概念、
   缺失证据的正确措辞、以及"本档案不成立什么"。

## 三条不可违背的呈现纪律

* **不把模型判断写成已证实的客观事实。** 所有结论都要标明它来自哪个模型、哪一步判断。
* **缺失证据 ≠ 造假。** 缺失只说明"现有证据不足以支持"，不构成"没做过"的判断。
* **不外推。** 一条主张的状态不能推广成"系统整体的能力评估可靠"。
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from . import adapter

# 复核模型独立性与证据来源独立性是两个不同维度，命名相近但含义无关，
# 必须分开呈现，否则会被误读。
INDEPENDENCE_NOTE = (
    "本档案涉及两个都叫“独立”但**毫不相关**的概念，不可互换：\n"
    "  - **复核模型独立**（`independent_verifier`）：做复核/裁决的模型是否与抽取模型不同。\n"
    "    衡量的是**复核机制**是否可能自我偏袒。\n"
    "  - **证据来源独立**（`evidence.independent_source`）：该主张的证据是否跨多个不同来源。\n"
    "    衡量的是**证据互证**程度。若两条证据都出自同一份文件，此项为 False，"
    "这是正确结果，不代表复核不独立。"
)

MISSING_EVIDENCE_NOTE = (
    "以下条目是攻击环节指出的**尚未确认**的信息。\n"
    "**缺失证据不等于造假**：它只说明现有材料不足以支持该主张，"
    "既不构成“用户没做过”的判断，也不构成“材料不实”的判断。\n"
    "要把它们变成结论，需要补充相应证据后重新评估。"
)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def build(store, claim_id: str, *, db_path: str, generated_by: str = "artifacts/m1e/run_dossier.py") -> dict:
    """装配一条主张的完整档案数据（不改写任何判断，只做组织与补充元信息）。"""
    raw = adapter.claim_dossier(store, claim_id)
    if raw is None:
        raise adapter.EvidenceError(f"未知主张: {claim_id}")

    claim = raw["claim"]
    counts = adapter.counts(store)
    metadata = claim.get("metadata") or {}

    # 按 passage 把「抽取」与「复核」两行证据配起来。
    # id 规则使它们天然成对：抽取 ev_<h>，复核 evv_<h>，h 相同即同一 passage。
    pairs: dict[str, dict] = {}
    for link in raw["evidence"]:
        key = link["passage_id"]
        entry = pairs.setdefault(key, {"extraction": None, "verification": None, "passage": {}})
        entry["passage"] = {
            "id": link["passage_id"],
            "ordinal": link.get("passage_ordinal"),
            "text": link.get("passage_text", ""),
            "source": link.get("source") or {},
            "source_assessment": link.get("source_assessment") or {},
        }
        if str(link.get("id", "")).startswith("evv_"):
            entry["verification"] = link
        else:
            entry["extraction"] = link

    return {
        "generated_at": _now(),
        "generated_by": generated_by,
        "db_path": str(db_path),
        "claim_id": claim_id,
        "claim": claim,
        "metadata": metadata,
        "pairs": pairs,
        "attacks": raw["attacks"],
        "conflicts": raw["conflicts"],
        "review_trail": raw["review_trail"],
        "scope": {
            "sources": counts.get("sources"),
            "passages": counts.get("passages"),
            "entities": counts.get("entities"),
            "claims": counts.get("claims"),
            "evidence": counts.get("evidence"),
            "attacks": counts.get("attack_reports", len(raw["attacks"])),
        },
    }


def _is_independent_source(dossier: dict) -> bool:
    return any(bool((entry["extraction"] or {}).get("independent_source")) for entry in dossier["pairs"].values())


def render(dossier: dict) -> str:
    claim = dossier["claim"]
    meta = dossier["metadata"]
    confidence = claim.get("confidence") or {}
    out: list[str] = []

    # 标题用三元组（简短可扫读）。不要把 claim 的 statement 当标题 ——
    # 那是整段论述，会变成一个无法阅读的一级标题；完整陈述放在第一节。
    subject = claim.get("subject") or "?"
    predicate = claim.get("predicate") or "?"
    obj = claim.get("object") or "?"
    if len(obj) > 44:
        obj = obj[:44] + "…"
    out.append(f"# 能力证据档案：{subject} —[{predicate}]-> {obj}")
    out.append("")

    # ---------- 生成信息（验收标准 5）----------
    out.append("## 生成信息")
    out.append(f"- **生成时间**：{dossier['generated_at']}")
    out.append(f"- **数据库**：`{dossier['db_path']}`")
    out.append(f"- **生成脚本**：`{dossier['generated_by']}`")
    scope = dossier["scope"]
    out.append(
        f"- **数据范围**：库中共 {scope['sources']} 个来源、{scope['passages']} 条段落、"
        f"{scope['claims']} 条主张、{scope['evidence']} 条证据行；**本档案只覆盖其中 1 条主张**"
    )
    out.append("- **分数呈现**：保留 3 位小数，便于直接与数据库逐字段对照")
    out.append("- **复核模型**：" + (meta.get("verifier_model") or "未记录"))
    out.append(
        "- **抽取所用模型**：**未记录在案**。抽取阶段没有把模型名写入数据库，"
        "因此此处无法给出历史事实 —— 当前配置值不作为该次抽取的记录。"
    )
    out.append("")

    # ---------- 一、主张与最终状态（验收标准 1）----------
    out.append("## 一、主张与最终状态")
    out.append(f"- **主张 ID**：`{claim.get('id')}`")
    out.append(f"- **陈述**：{claim.get('statement', '')}")
    out.append(f"- **三元组**：{subject} —[{predicate}]-> {claim.get('object')}")
    out.append(f"- **最终状态**：**`{claim.get('status')}`**")
    out.append(f"- **综合置信度**：{_fmt(confidence.get('score'))}")
    out.append(
        f"  - 来源可靠性 {_fmt(confidence.get('source_reliability'))}"
        f"｜抽取质量 {_fmt(confidence.get('extraction_quality'))}"
        f"｜互证 {_fmt(confidence.get('corroboration'))}"
        f"｜矛盾惩罚 {_fmt(confidence.get('contradiction_penalty'))}"
    )
    out.append(f"  - 分级状态：`{confidence.get('assessment_status')}`")
    if confidence.get("rationale"):
        out.append(f"  - 依据：{confidence['rationale']}")
    if meta.get("review_state"):
        out.append(f"- **复核处置**：`{meta.get('review_state')}`")
    out.append("")

    # ---------- 二、证据链（验收标准 2）----------
    out.append("## 二、证据链（按环节顺序）")

    out.append("### 1. 原始来源")
    seen_sources: dict[str, dict] = {}
    for entry in dossier["pairs"].values():
        source = entry["passage"].get("source") or {}
        if source.get("id"):
            seen_sources[source["id"]] = source
    for source in seen_sources.values():
        out.append(
            f"- `{source.get('id')}` **{source.get('title')}**"
            f"｜evkg 类型 `{source.get('kind')}`｜来源：{source.get('url') or '-'}"
        )
    if not seen_sources:
        out.append("（无）")

    out.append("")
    out.append("### 2. 段落与逐字摘录")
    for entry in dossier["pairs"].values():
        passage = entry["passage"]
        source_kind = (passage.get("source") or {}).get("kind", "?")
        out.append(
            f"- `{passage['id']}`（第 {passage.get('ordinal')} 段，来源类型 `{source_kind}`，"
            f"基线 {_fmt((passage.get('source_assessment') or {}).get('baseline_score'))}）"
        )
        quote = (entry["extraction"] or {}).get("quote") or passage.get("text", "")
        for line in str(quote).splitlines()[:6]:
            out.append(f"  > {line}")
        if len(str(quote).splitlines()) > 6:
            out.append(f"  > ……（共 {len(str(quote).splitlines())} 行）")

    out.append("")
    out.append("### 3. 抽取结果（模型产出，非事实）")
    for entry in dossier["pairs"].values():
        extraction = entry["extraction"] or {}
        out.append(
            f"- `{entry['passage']['id']}`：polarity=`{extraction.get('polarity')}`"
            f"，抽取置信 {_fmt(extraction.get('confidence'))}"
        )
        if extraction.get("reasoning"):
            out.append(f"  - 抽取说明：{extraction['reasoning']}")

    out.append("")
    out.append("### 4. 独立复核意见（另一模型产出，非事实）")
    any_verification = False
    for entry in dossier["pairs"].values():
        verification = entry["verification"]
        if not verification:
            continue
        any_verification = True
        out.append(
            f"- `{entry['passage']['id']}`：**polarity=`{verification.get('polarity')}`**"
            f"，复核置信 {_fmt(verification.get('confidence'))}"
        )
        if verification.get("reasoning"):
            out.append(f"  - 复核意见：{verification['reasoning']}")
    if not any_verification:
        out.append("（本主张尚无复核意见）")

    out.append("")
    out.append("### 5. 对抗攻击与裁决（复核模型裁决）")
    if dossier["attacks"]:
        for attack in dossier["attacks"]:
            verdict = attack.get("verdict") or {}
            probe = attack.get("probe") or {}
            out.append(f"- **质疑角度**：{probe.get('angle', '-')}")
            out.append(f"  - 质疑：{probe.get('question') or '(未记录问题)'}")
            out.append(f"  - **裁决：`{verdict.get('verdict', attack.get('verdict', '?'))}`**")
            if verdict.get("reasoning"):
                out.append(f"  - 裁决理由：{verdict['reasoning']}")
            if attack.get("created_at"):
                out.append(f"  - 时间：{attack['created_at']}")
    else:
        out.append("（本主张未被对抗攻击）")

    out.append("")
    out.append("### 6. 最终状态如何得到")
    out.append(
        "上述各步都是**模型的判断**，不是已被证实的事实。最终状态由这些判断合并而来："
    )
    out.append("- 抽取阶段把状态置为 `extracted`（此时尚无任何复核）")
    if any_verification:
        out.append("- 独立复核给出 polarity 与复核置信，并按证据是否充分决定是否转为 `machine_reviewed`")
    if dossier["attacks"]:
        verdicts = [((a.get("verdict") or {}).get("verdict") or a.get("verdict")) for a in dossier["attacks"]]
        out.append(f"- 对抗裁决为 {verdicts}；出现 `broken` 时主张被置为 `disputed`")
    out.append(f"- **当前状态：`{claim.get('status')}`** —— 这是一个可复核的判断，而非定论")
    out.append("")

    # ---------- 三、缺失证据（验收标准 3）----------
    missing: list[tuple[str, list[str]]] = []
    for attack in dossier["attacks"]:
        verdict = attack.get("verdict") or {}
        items = verdict.get("missing_evidence") or []
        if items:
            missing.append((verdict.get("verdict", "?"), items))
    out.append("## 三、尚未确认的证据（不等于造假）")
    out.append(MISSING_EVIDENCE_NOTE)
    out.append("")
    if missing:
        for verdict_name, items in missing:
            out.append(f"**来自 `{verdict_name}` 裁决**：")
            for item in items:
                out.append(f"- {item}")
            out.append("")
    else:
        out.append("（攻击环节未列出缺失证据）")
        out.append("")

    # ---------- 四、两个"独立"（验收标准 4）----------
    out.append("## 四、两类“独立”的取值与含义")
    out.append(INDEPENDENCE_NOTE)
    out.append("")
    out.append(f"- `independent_verifier = {meta.get('verifier_independent')}`"
               f"（复核模型：{meta.get('verifier_model') or '未记录'}）")
    out.append(f"- `evidence.independent_source = {_is_independent_source(dossier)}`"
               f"（本主张的证据是否跨多个来源）")
    out.append("")

    # ---------- 五、证据局限（验收标准 2 后半 + 5）----------
    out.append("## 五、本档案不成立的结论")
    out.append("为避免把模型判断读成事实，明确列出**本档案不能支持**的推论：")
    out.append("- 不能得出“用户具备该能力”的结论 —— 档案只呈现证据是否充分，不代替能力评级。")
    out.append(
        "- 不能由“项目存在”推出“用户个人实现”：本库的归属层尚未建立，"
        "`repo_artifact` 等材料只能证明材料本身的内容。"
    )
    out.append("- 不能把本条主张的状态推广为“系统的能力评估整体可靠”的结论。")
    out.append("- 不能把缺失证据读作造假或未做过。")
    out.append("")

    # ---------- 附：处理轨迹 ----------
    trail = dossier["review_trail"]
    if trail:
        out.append("## 附：原始审计轨迹")
        for item in trail[:20]:
            out.append(f"- {item['at']} `{item['action']}`")
        out.append("")

    return "\n".join(out) + "\n"


def _fmt(value) -> str:
    """分数呈现：保留 3 位小数。

    为什么不是 2 位：档案的价值之一是"可对照数据库复核"。2 位会把库中的 0.697 显示成
    0.70，读者拿去比对就会对不上 —— 对一个证据文档而言这是失真。3 位足以覆盖本库所有
    取值的精度，同时在页面上仍然可读。约定写在"生成信息"里，读者知道如何解读。
    """
    if value is None:
        return "-"
    try:
        return f"{float(value):.3f}"
    except (TypeError, ValueError):
        return str(value)


def write(store, claim_id: str, output: str | Path, *, db_path: str, generated_by: str | None = None) -> dict:
    dossier = build(store, claim_id, db_path=db_path, **({"generated_by": generated_by} if generated_by else {}))
    markdown = render(dossier)
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown, encoding="utf-8")
    return {"claim_id": claim_id, "output": str(path), "markdown": markdown, "dossier": dossier}
