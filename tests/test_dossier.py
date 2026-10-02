"""M1-e：证据档案（dossier）的行为测试。

用户锁定的五条验收标准，在这里被固化成可重跑的断言：

1. 主张状态可追溯    -> 档案呈现最终状态与置信度，且与库中一致
2. 证据链完整        -> 六个环节齐全；**模型判断标注为判断而非事实**
3. 缺失证据明确      -> 单列且声明"不等于造假"
4. 状态语义准确      -> 两个"独立"分别给出取值与含义
5. 可验收产物        -> 含生成时间/范围/局限；与库一致

另有一条针对已知上游缺陷的回归测试：**`partial` 极性的证据必须被呈现**
（evkg 自带的 `render_claim_markdown` 只输出 supports/refutes，会漏掉它）。

合成数据用临时库，保证可移植；另有一条 `skipif` 用例核对仓库里真实产出的档案
与本机真实库是否一致（真实库已 gitignore，缺失时自动跳过）。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from growth_os.evidence import adapter, dossier

REPO_ROOT = Path(__file__).resolve().parents[1]
REAL_DB = REPO_ROOT / "data" / "growth.db"
REAL_DOSSIERS = REPO_ROOT / "artifacts" / "m1e"

QUOTE = "本项目使用 ChromaDB 实现语义检索，召回率从 65% 提升至 92%。"
VERIFIER_OPINION = "原文只能证明项目包含检索模块，不能证明用户本人实现，故仅部分支持。"


@pytest.fixture()
def store(tmp_path: Path):
    return adapter.open_store(tmp_path / "dossier.db")


def _seed(store, *, with_attacks: bool = True, with_verification: bool = True) -> str:
    """造一条：抽取 supports → 复核 partial → 对抗 broken 的主张。"""
    adapter.configure()
    source = store.get_source("src_demo")
    if source is None:
        from evkg.domain import Source, SourceKind

        store.save_source(
            Source(id="src_demo", title="示例 README", kind=SourceKind.PRIMARY,
                   metadata={"assessment": {"baseline_score": 0.82}, "growth_evidence_type": "repo_artifact"})
        )
    from evkg.domain import Passage

    passage = Passage(id="p_demo", source_id="src_demo", ordinal=0, text=QUOTE,
                      locator={"ordinal": 0}, text_hash="h")
    store.save_passages([passage])

    from evkg.domain import Claim, ClaimStatus, Confidence, EvidenceLink, Polarity

    claim_id = "clm_demo"
    store.save_claim(
        Claim(
            id=claim_id, subject="用户", predicate="实现过", object="RAG 检索",
            statement="用户实现过 RAG 检索。", status=ClaimStatus.DISPUTED,
            confidence=Confidence(score=0.17, source_reliability=0.82, extraction_quality=0.35,
                                  resolution_quality=0.25, corroboration=0.0, contradiction_penalty=0.0,
                                  assessment_status="assessed", rationale="复核仅部分支持。"),
            passage_ids=[passage.id],
            metadata={"review_state": "disputed_by_adversarial", "verifier_model": "demo-verifier",
                      "verifier_independent": True},
        )
    )
    store.save_evidence(EvidenceLink(id="ev_demo", claim_id=claim_id, passage_id=passage.id,
                                    polarity=Polarity.SUPPORTS, quote=QUOTE,
                                    reasoning="候选主张的原文绑定", confidence=0.35))
    if with_verification:
        store.save_evidence(EvidenceLink(id="evv_demo", claim_id=claim_id, passage_id=passage.id,
                                        polarity=Polarity.PARTIAL, quote=QUOTE,
                                        reasoning=VERIFIER_OPINION, confidence=0.17))
    if with_attacks:
        # attack_reports 只有私有写入方法，测试夹具直接用 SQL 造行。
        store.db.execute(
            "CREATE TABLE IF NOT EXISTS attack_reports (id TEXT PRIMARY KEY, task_id TEXT NOT NULL,"
            " kind TEXT NOT NULL, target_id TEXT NOT NULL, payload TEXT NOT NULL,"
            " created_at TEXT DEFAULT CURRENT_TIMESTAMP)"
        )
        store.db.execute(
            "INSERT INTO attack_reports(id,task_id,kind,target_id,payload) VALUES(?,?,?,?,?)",
            ("rep_demo", "t", "adversarial", claim_id, json.dumps({
                "probe": {"target_claim_id": claim_id, "angle": "用户角色不明",
                          "question": "这是个人独立完成、团队协作还是照抄教程？"},
                "verdict": {"target_claim_id": claim_id, "verdict": "broken",
                            "reasoning": "将项目存在等同于用户个人实现。",
                            "missing_evidence": ["用户本人在项目中的角色说明", "代码提交记录或署名"]},
            }, ensure_ascii=False)),
        )
        store.db.commit()
    return claim_id


def _render(store, claim_id: str) -> str:
    return dossier.render(dossier.build(store, claim_id, db_path=":memory:"))


# ---------------------------------------------------------------------------
# 验收标准 2：证据链完整 + 判断不等于事实
# ---------------------------------------------------------------------------


def test_renders_six_step_evidence_chain(store):
    markdown = _render(store, _seed(store))
    for section in ("### 1. 原始来源", "### 2. 段落与逐字摘录", "### 3. 抽取结果",
                    "### 4. 独立复核意见", "### 5. 对抗攻击与裁决", "### 6. 最终状态如何得到"):
        assert section in markdown, f"缺少环节：{section}"


def test_model_judgements_are_labelled_as_judgements(store):
    markdown = _render(store, _seed(store))
    assert "模型产出，非事实" in markdown
    assert "上述各步都是**模型的判断**，不是已被证实的事实" in markdown
    assert "这是一个可复核的判断，而非定论" in markdown


def test_verbatim_quote_appears(store):
    markdown = _render(store, _seed(store))
    assert QUOTE in markdown, "逐字摘录缺失"


def test_adversarial_question_and_verdict_appear(store):
    markdown = _render(store, _seed(store))
    assert "这是个人独立完成、团队协作还是照抄教程？" in markdown
    assert "`broken`" in markdown
    assert "将项目存在等同于用户个人实现。" in markdown


def test_final_status_explains_derivation(store):
    markdown = _render(store, _seed(store))
    assert "抽取阶段把状态置为 `extracted`" in markdown
    assert "出现 `broken` 时主张被置为 `disputed`" in markdown


# ---------------------------------------------------------------------------
# ★ 回归：partial 极性不得被漏掉（evkg 自带渲染器的缺陷）
# ---------------------------------------------------------------------------


def test_partial_polarity_evidence_is_rendered(store):
    """这是本模块存在的直接原因。

    evkg 的 `render_claim_markdown` 只渲染 supports / refutes 两个列表，
    `partial` 会落在两者之外 —— 而被推翻的那条真实主张恰恰是 partial。
    若哪天有人把这里的渲染换成 evkg 的原版，本用例会立刻变红。
    """
    markdown = _render(store, _seed(store))
    assert "polarity=`partial`" in markdown, "partial 极性的复核证据被漏掉了"
    assert VERIFIER_OPINION in markdown, "复核意见正文缺失"


def test_partial_is_not_listed_as_support(store):
    """partial 不能被误标成支持或反对。"""
    markdown = _render(store, _seed(store))
    assert "**polarity=`partial`**" in markdown
    assert "反对证据" not in markdown, "partial 不应被当成反对证据渲染"


# ---------------------------------------------------------------------------
# 验收标准 1：主张状态可追溯
# ---------------------------------------------------------------------------


def test_status_and_score_match_database(store):
    claim_id = _seed(store)
    markdown = _render(store, claim_id)
    claim = store.get_claim(claim_id) if hasattr(store, "get_claim") else next(
        c for c in store.get_claims() if c.id == claim_id
    )
    assert f"`{claim.status.value}`" in markdown
    assert f"{float(claim.confidence.score):.3f}" in markdown
    assert f"{float(claim.confidence.source_reliability):.3f}" in markdown


def test_review_disposition_is_shown(store):
    markdown = _render(store, _seed(store))
    assert "disputed_by_adversarial" in markdown


# ---------------------------------------------------------------------------
# 验收标准 3：缺失证据明确，且不等于造假
# ---------------------------------------------------------------------------


def test_missing_evidence_listed_separately(store):
    markdown = _render(store, _seed(store))
    assert "## 三、尚未确认的证据（不等于造假）" in markdown
    assert "用户本人在项目中的角色说明" in markdown
    assert "代码提交记录或署名" in markdown


def test_missing_evidence_is_not_framed_as_fabrication(store):
    markdown = _render(store, _seed(store))
    assert "**缺失证据不等于造假**" in markdown
    assert "既不构成“用户没做过”的判断" in markdown
    assert "也不构成“材料不实”的判断" in markdown


# ---------------------------------------------------------------------------
# 验收标准 4：两个"独立"分开呈现
# ---------------------------------------------------------------------------


def test_two_independence_concepts_are_distinguished(store):
    markdown = _render(store, _seed(store))
    assert "independent_verifier = True" in markdown
    assert "evidence.independent_source = False" in markdown
    assert "不可互换" in markdown
    assert "不代表复核不独立" in markdown


def test_independent_verifier_value_comes_from_metadata(store):
    """取值必须来自 claim.metadata（事实），而不是渲染时重新推断。"""
    claim_id = _seed(store)
    store.db.execute(
        "UPDATE claims SET payload = json_set(payload,'$.metadata.verifier_independent',0) WHERE id=?",
        (claim_id,),
    )
    store.db.commit()
    assert "independent_verifier = 0" in _render(store, claim_id)


# ---------------------------------------------------------------------------
# 验收标准 5：可验收产物（元信息 + 局限）
# ---------------------------------------------------------------------------


def test_generation_metadata_present(store):
    markdown = _render(store, _seed(store))
    for field in ("**生成时间**", "**数据库**", "**生成脚本**", "**数据范围**", "**分数呈现**"):
        assert field in markdown, f"缺少生成信息字段：{field}"


def test_extraction_model_absence_is_disclosed_not_faked(store):
    """抽取模型没入库，就必须说"未记录"，不能拿当前配置冒充历史事实。"""
    markdown = _render(store, _seed(store))
    assert "**未记录在案**" in markdown
    assert "当前配置值不作为该次抽取的记录" in markdown


def test_recorded_extractor_model_is_shown(store):
    """C5 之后：库里记了抽取 provenance，档案必须显示它（不再说"未记录"）。"""
    claim_id = _seed(store)
    claim = next(item for item in store.get_claims() if item.id == claim_id)
    claim.metadata = {
        **claim.metadata,
        "extractor_provider": "openai_compatible",
        "extractor_model": "glm-5.3-flash",
        "extractor_prompt_hash": "abc123def4567890",
        "extractor_profile": "growth_os",
    }
    store.save_claim(claim)
    markdown = _render(store, claim_id)
    assert "`glm-5.3-flash`" in markdown
    assert "abc123def4567890" in markdown
    assert "未记录在案" not in markdown


def test_limitations_section_present(store):
    markdown = _render(store, _seed(store))
    assert "## 五、本档案不成立的结论" in markdown
    assert "不能得出“用户具备该能力”的结论" in markdown
    assert "本库的归属层尚未建立" in markdown
    assert "不能把本条主张的状态推广为“系统的能力评估整体可靠”的结论" in markdown
    assert "不能把缺失证据读作造假或未做过" in markdown


def test_title_uses_triple_not_full_statement(store):
    """一级标题必须是可扫读的三元组，不能是整段 statement。"""
    markdown = _render(store, _seed(store))
    title = markdown.splitlines()[0]
    assert title.startswith("# 能力证据档案：用户 —[实现过]->")
    statement = next(c for c in store.get_claims() if c.id == "clm_demo").statement
    assert statement not in title, "标题里塞进了整段陈述"


# ---------------------------------------------------------------------------
# 边界：缺攻击 / 缺复核 / 未知主张
# ---------------------------------------------------------------------------


def test_claim_without_attacks_says_so(store):
    markdown = _render(store, _seed(store, with_attacks=False))
    assert "（本主张未被对抗攻击）" in markdown
    assert "（攻击环节未列出缺失证据）" in markdown


def test_claim_without_verification_says_so(store):
    markdown = _render(store, _seed(store, with_verification=False))
    assert "（本主张尚无复核意见）" in markdown


def test_unknown_claim_raises(store):
    with pytest.raises(adapter.EvidenceError, match="未知主张"):
        dossier.build(store, "clm_does_not_exist", db_path=":memory:")


def test_write_creates_file(store, tmp_path):
    claim_id = _seed(store)
    result = dossier.write(store, claim_id, tmp_path / "out" / "d.md", db_path=":memory:")
    assert Path(result["output"]).is_file()
    assert Path(result["output"]).read_text(encoding="utf-8") == result["markdown"]


# ---------------------------------------------------------------------------
# 真实产物与真实库的一致性（真实库已 gitignore，缺失则跳过）
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not REAL_DB.is_file(), reason="本机没有真实证据库")
def test_committed_dossiers_match_real_database():
    """仓库里提交的档案必须与真实库逐项一致 —— 防止档案与事实脱节。"""
    adapter.configure()
    store = adapter.open_store(str(REAL_DB))
    try:
        claims = store.get_claims()
        assert claims, "真实库中没有主张"
        for claim in claims:
            path = REAL_DOSSIERS / f"dossier-{claim.id.replace('clm_', '')}.md"
            assert path.is_file(), f"缺少已提交的档案：{path.name}"
            markdown = path.read_text(encoding="utf-8")
            assert f"`{claim.id}`" in markdown
            assert f"`{claim.status.value}`" in markdown
            assert f"{float(claim.confidence.score):.3f}" in markdown
            assert f"independent_verifier = {claim.metadata.get('verifier_independent')}" in markdown
            raw = adapter.claim_dossier(store, claim.id)
            for link in raw["evidence"]:
                if link.get("polarity") == "partial" and link.get("reasoning"):
                    assert link["reasoning"] in markdown, "真实 partial 复核意见未呈现"
    finally:
        store.db.close()
