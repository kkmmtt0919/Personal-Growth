"""只读核对已归档验收证据，生成缺口清单；不把历史通过当成本轮重跑。"""

from __future__ import annotations

import hashlib
import html
import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts" / "m8" / "acceptance-audit"


def load(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def fingerprint(relative: str) -> dict:
    path = ROOT / relative
    return {"path": relative, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    session = load("artifacts/m2/session-real.json")
    trace = load("artifacts/gates/G2/traceability.json")
    audit = load("artifacts/gates/G2/audit.json")
    comparison = load("artifacts/gates/G3/comparison.json")
    g4 = load("artifacts/gates/G4/checks.json")
    g5 = load("artifacts/gates/G5/checks.json")
    m4 = load("artifacts/gates/M4/m4-gate-result.json")
    m5 = load("artifacts/gates/M5/m5-gate-result.json")
    demo = load("artifacts/m8/verification.json")
    rounds = session["clarification"]["rounds"]
    goal = session["goal"]
    checks = {
        "G1": session["mode"] == "real" and session["all_checks_passed"] is True
        and 1 <= len(rounds) <= 6 and goal["status"] == "confirmed"
        and all(goal[key] for key in ("direction", "purpose", "horizon", "measurable_result")),
        "G2": trace["sample_count"] >= 5 and trace["all_traceable_complete"] is True
        and audit["status"] == "pass" and audit["total_violations"] == 0,
        "G3": comparison["passed"] is True and m4["all_checks_passed"] is True,
        "G4": g4["all_checks_passed"] is True and all(g4["checks"].values()),
        "G5": g5["all_checks_passed"] is True and all(g5["checks"].values())
        and g5["requests"] > 0 and m5["all_checks_passed"] is True,
    }
    paths = {
        "G1": ["artifacts/m2/session-real.json", "artifacts/gates/G1/README.md"],
        "G2": ["artifacts/gates/G2/traceability.json", "artifacts/gates/G2/audit.json"],
        "G3": ["artifacts/gates/G3/comparison.json", "artifacts/gates/M4/m4-gate-result.json"],
        "G4": ["artifacts/gates/G4/checks.json"],
        "G5": ["artifacts/gates/G5/checks.json", "artifacts/gates/M5/m5-gate-result.json"],
    }
    notes = {
        "G1": "真实模型历史会话；本轮生成明确标注的历史回放，非实时交互截图。",
        "G2": "历史记录为全量七条追溯、确定性取五条；不是原文所称随机抽样。",
        "G3": "执行基线允许实践无证据为 NULL；材料主体为 RAG。原始示例与执行口径不同。",
        "G4": "两条接受、四条反例拒绝；任务质量不等于学习价值。",
        "G5": "历史真实生成/绑定闭环；本轮 M8 受控预设任务不能代替该门。",
    }
    gates = {
        gate: {"status": "recorded_pass" if passed else "recorded_evidence_failed",
               "reexecuted_this_audit": False,
               "evidence": [fingerprint(path) for path in paths[gate]], "note": notes[gate]}
        for gate, passed in checks.items()
    }
    gates["G6"] = {
        "status": "not_verified", "reexecuted_this_audit": False,
        "evidence": [],
        "missing": ["持久化的前后快照差异", "隔天重新打开后的 Growth Agent 输出",
                    "下一步建议与 open gap/task 的来源", "长期偏好来源引用", "会话截图"],
        "note": "Memory/Proactive 测试通过不能替代隔天返回验收。",
    }
    result = {
        "audit_date": "2026-10-05", "head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "working_tree_modified": bool(subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()),
        "audit_completed": True, "full_mvp_accepted": False, "gates": gates,
        "quality_gates": {
            "QG1_QG2_QG3_QG4": "M4/M5 历史封板记录通过；本轮未重新执行生产质量门",
            "QG5": {"growth_os": demo["validation"],
                    "evkg": "本阶段未重新运行上游测试，完整封板前需核对/重跑"},
        },
        "open_product_scope": ["实时目标澄清界面", "产品上传与 PDF 页码定位",
                               "GitHub OAuth/私有仓库", "Evidence 攻击详情展示",
                               "AI Mentor", "外部通知与目标自动重建"],
        "source_code": [fingerprint(path) for path in [
            "scripts/audit_mvp_acceptance.py", "backend/growth_os/memory/projection.py",
            "backend/growth_os/proactive/analyzer.py"]],
    }
    regression = OUTPUT / "boundary-regression.xml"
    if regression.is_file():
        suites = ET.parse(regression).getroot().iter("testsuite")
        totals = {key: 0 for key in ("tests", "failures", "errors", "skipped")}
        for suite in suites:
            for key in totals:
                totals[key] += int(suite.get(key, "0"))
        result["boundary_regression"] = {
            **totals, "passed": totals["tests"] - sum(totals[key] for key in
                                                     ("failures", "errors", "skipped")),
            "evidence": fingerprint(regression.relative_to(ROOT).as_posix()),
        }
    result["visual_supplement"] = [fingerprint(path) for path in [
        "artifacts/gates/G1/session-replay.png"] if (ROOT / path).is_file()]
    (OUTPUT / "result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    rows = "\n".join(f"| {gate} | {item['status']} | {item['note']} |"
                     for gate, item in gates.items())
    (OUTPUT / "README.md").write_text(
        "# M8-d · MVP 验收缺口核对\n\n2026-10-05。核对完成；完整 MVP 尚未验收。\n\n"
        "运行：`.\\.venv\\Scripts\\python.exe scripts/audit_mvp_acceptance.py`。"
        "此命令读归档证据、记录哈希并生成报告；不调用模型、不改数据库。"
        "历史记录没有被本轮重新执行，不自动续期。\n\n"
        "| 门 | 状态 | 证据限制 |\n|---|---|---|\n" + rows + "\n\n"
        "## 下一阶段：G6-a 最小返回契约\n\n"
        "从持久化 assessment 快照比较理解/实践的变化；长期偏好只引用已确认 profile memory。"
        "返回输出包含变化摘要、当前 open gap/已有任务与下一步、每项来源标识。"
        "使用可注入时钟模拟隔天，并先关闭再重新打开存储，证明来源于持久化数据。\n\n"
        "反例：没有基线不能说有提升；无新证据不能因 done 升星；没有偏好不能编造；"
        "理解/实践不能混合；未知目标和不匹配快照拒绝。"
        "G6-a 只做契约与只读输出，不扩展 Mentor Chat、自动规划、Memory 演化或主动通知。"
        "后续 G6-b 做隔天持久化验收与页面补证，最后再核对全量质量门。\n\n"
        "原始 G2 随机取样、G3 示例与已冻结执行基线的差别保留在案；"
        "不在本报告中静默改判定标准。依赖归档刷新、发布 pin 和独立验收库自举仍需核对。\n",
        encoding="utf-8")
    blocks = []
    for turn in rounds:
        blocks.append(f"<article><h2>第 {turn['round']} 轮</h2>"
                      f"<p><b>系统：</b>{html.escape(turn['question'])}</p>"
                      f"<p><b>用户：</b>{html.escape(turn['answer'])}</p></article>")
    fields = "".join(f"<li><b>{label}：</b>{html.escape(goal[key])}</li>"
                     for key, label in [("direction", "方向"), ("purpose", "目的"),
                                        ("horizon", "时间周期"), ("measurable_result", "可衡量结果")])
    replay = """<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<title>G1 历史会话回放</title><style>
body{font:17px/1.7 'Microsoft YaHei',sans-serif;background:#faf7f2;color:#3f3a34;margin:32px auto;max-width:1040px;padding:0 24px}
article,section{background:white;border:1px solid #eadfd2;border-radius:8px;padding:14px 22px;margin:14px 0}
h1{font-size:28px}h2{font-size:19px;margin:0}p{margin:9px 0}.note{color:#a95220}li{margin:6px 0}
</style><h1>G1 · 目标澄清：历史会话回放</h1>
<p class="note">历史记录展示，非实时交互。会话发生于 2026-10-02；回放生成于 2026-10-05。</p>
<p>系统使用真实模型，用户应答来自确定性测试脚本。来源：artifacts/m2/session-real.json。</p>
""" + "".join(blocks) + f"<section><h2>已确认目标</h2><ul>{fields}</ul>"
    replay += f"<p>确认原话：{html.escape(goal['source_quote'])}</p>"
    replay += f"<p>源文件 SHA-256：{fingerprint(paths['G1'][0])['sha256']}</p></section></html>"
    (ROOT / "artifacts/gates/G1/session-replay.html").write_text(replay, encoding="utf-8")
    print(json.dumps({"audit_completed": True, "recorded_gates": checks,
                      "G6": "not_verified", "full_mvp_accepted": False}, ensure_ascii=False))


if __name__ == "__main__":
    main()
