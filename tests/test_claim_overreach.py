"""M3-a：越权校验的测试 —— **"存在证据" ≠ "证明能力"**（`M3-PLAN.md` v1.0 §1）。

边界（用户明确指定）：本步只验证**检查器**的行为；把检查接进写入路径、
以及处理 M1-c 那条历史上的用户口径主张，都是 M3-e 的工作 —— 这里不追改历史数据。
"""

from __future__ import annotations

import pytest
from growth_os.evidence.claims import (
    ACHIEVEMENT_MARKERS,
    USER_SUBJECT_MARKERS,
    check_overreach,
)

# M1-c 真实抽取产出的那条主张（后被 M4 的攻击环节推翻）—— 作为"必须被判越权"的样本
HISTORICAL_CLAIM = {
    "statement": (
        "原文（README）描述的项目 MYtest 中实现了 RAG 检索服务、AI 调用服务、测试用例生成等模块，"
        "但未明确用户本人在项目中的具体角色与贡献，能力主张仅基于项目描述本身。"
    ),
    "subject": "用户",
    "predicate": "实现过",
}

# M3 允许的写法：材料口径 —— 同样的材料，结论只说到"材料里有什么"
ALLOWED_CLAIM = {
    "statement": "项目材料中出现 RAG 检索服务的实现相关内容（RagService.java、ChromaDB 依赖）",
    "subject": "MYtest 项目",
    "predicate": "包含",
}


def test_historical_user_scoped_claim_is_flagged_as_overreach():
    """M1-c 那条主张：主语是用户 + 成就类谓词 → 越权（本步只判定，不追改）。"""
    report = check_overreach(**HISTORICAL_CLAIM)
    assert report.overreach is True
    assert any("实现过" in reason for reason in report.reasons)


def test_material_scoped_formulation_is_allowed():
    """同样的材料，材料口径的表述合规 —— 这正是 M3 允许产出的形态。"""
    report = check_overreach(**ALLOWED_CLAIM)
    assert report.overreach is False
    assert report.reasons == ()


@pytest.mark.parametrize(
    "predicate",
    ["具备", "掌握", "精通", "擅长", "独立完成", "独立实现", "负责过", "主导", "搭建过"],
)
def test_user_subject_with_achievement_predicate_is_overreach(predicate):
    report = check_overreach(statement=f"用户{predicate}了某项能力", subject="用户", predicate=predicate)
    assert report.overreach is True


@pytest.mark.parametrize(
    "statement",
    [
        "用户具备 RAG 能力",
        "本人独立完成了该项目",
        "我掌握 Agent Memory 的实现",
        "用户能独立搭建检索服务",
    ],
)
def test_user_first_person_statements_are_overreach_even_without_triple(statement):
    """陈述本身以用户为主语且含成就词 → 越权（不依赖 subject 字段是否填写）。"""
    assert check_overreach(statement=statement).overreach is True


def test_user_capability_level_is_overreach():
    """星级/等级属于 M4：M3 的用户口径陈述里出现等级表述即越权。"""
    for statement in (
        "用户 RAG 能力 4/5",
        "用户实践能力为 4 星",
        "用户该能力等级 3，证据充分",
    ):
        report = check_overreach(statement=statement, subject="用户")
        assert report.overreach is True
        assert any("等级" in reason or "星级" in reason for reason in report.reasons)


def test_material_achievement_is_not_user_overreach():
    """材料/项目本身的成就表述不算越权（"项目实现了 X" ≠ "用户实现了 X"）。"""
    report = check_overreach(
        statement="项目实现了 RAG 检索与测试用例生成", subject="MYtest 项目", predicate="实现过"
    )
    assert report.overreach is False


def test_weak_self_reports_are_not_capability_conclusions():
    """自述"计划学习 / 有所了解"不是能力结论：M3 可以记录（作为弱证据材料内容）。"""
    for statement in (
        "对话材料中出现用户计划学习 Agent Evaluation 的自述",
        "用户自述对 rerank 只是看过论文、尚未实现",
    ):
        assert check_overreach(statement=statement).overreach is False


def test_material_scoped_statement_mentioning_user_role_gap_is_allowed():
    """材料口径 + 明确标注角色缺失：合规（这是 M1-c 抽取器自己写的那句限定语）。"""
    report = check_overreach(
        statement="原文描述的项目包含 RAG 模块；未明确用户本人在项目中的角色与贡献",
        subject="MYtest 项目",
        predicate="包含",
    )
    assert report.overreach is False


def test_vocabulary_is_locked_and_documented():
    """词汇表被测试锁定：新增/删除标记词必须显式改这里，避免门槛被悄悄放松。"""
    assert "用户" in USER_SUBJECT_MARKERS
    assert {"具备", "掌握", "实现过", "独立完成"} <= set(ACHIEVEMENT_MARKERS)

def test_negated_achievement_markers_are_not_overreach():
    """否定语境不算命中 —— 实测教训（M3-e 历史主张 dry-run）。

    真实库里那条正确的"计划学习"主张，陈述写着"…不代表已具备相应能力"；
    若把否定词后的「具备」当成越权命中，写入闸门会挡掉合法表述。
    """
    historical_good = {
        "statement": (
            "原文「未来规划」列出支持 Dubbo、gRPC 的 MCP 工具扩展、接入本地大模型等，"
            "仅为计划事项，不代表已具备相应能力。"
        ),
        "subject": "用户",
        "predicate": "计划学习",
    }
    report = check_overreach(**historical_good)
    assert report.overreach is False and report.reasons == ()


@pytest.mark.parametrize(
    "statement",
    [
        "项目材料中没有实现过向量检索优化",
        "材料显示尚未完成独立部署",
        "该资料未表明用户掌握 Kubernetes",
        "原文仅是计划，不代表已经具备相关能力",
    ],
)
def test_negated_statements_do_not_trip_the_gate(statement):
    assert check_overreach(statement=statement, subject="项目材料", predicate="包含").overreach is False


def test_unnegated_assertion_still_trips_the_gate():
    """反向保证：去掉否定词后必须仍然命中（阈值没有被改松）。"""
    assert check_overreach(statement="用户已经具备 RAG 能力", subject="用户").overreach is True
    assert check_overreach(
        statement="材料描述该用户实现过向量检索优化", subject="用户", predicate="实现过"
    ).overreach is True
