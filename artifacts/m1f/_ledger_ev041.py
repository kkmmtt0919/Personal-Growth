"""一次性：登记 EV-041 与测试数修正。"""

import pathlib

OPEN, CLOSE = "\u300c", "\u300d"  # 明确用中文引号，避免与 Python 字符串定界符冲突

p = pathlib.Path(".project-to-act/PROJECT_ACCEPTANCE.md")
s = p.read_text(encoding="utf-8")

s = s.replace("`tests/test_damage_selftest.py` `928aa0374777` | **8 passed**",
              "`tests/test_damage_selftest.py` `7c4ed1888835` | **10 passed**")

anchor = "| EV-040 | 2026-10-01 | 真实库未被触碰 + 全量回归 | pass | `data/growth.db`；Growth OS 71 项 / evkg 101 项 |"
idx = s.index(anchor)
end = s.index("\n", idx)
ev = s[idx:end]

new_ev = (
    ev
    + "\n| EV-041 | 2026-10-01 | **内容级**恢复核对 `artifacts/m1f/verify_no_content_change.py`（计数级加固） | exit 0 | "
    "script `b782aa143533`；`recovery_content_check.json` `94fe6e6d71a4` | **通过**。按用户给定最小攻击重跑："
    "基线 sources=3 / passages=109 / claims=2 / evidence=6 / audit=PASS → 注入（已存在 claim+source、"
    "`passage_id=p_nonexistent`、引文 " + CLOSE + "代码证明用户完成实现" + CLOSE + "）→ "
    "`evidence_missing_passage` 0→1、audit=FAIL → 清理后四张表**逐行 payload sha256 完全一致**"
    "（新增 0 / 删除 0 / 内容变更 0）、audit 回到 PASS/0；真实库同样**内容级一致**。"
    "补这一步的原因：计数级核对验不出" + OPEN + "条数不变但既有行被改写" + CLOSE + " | "
    "命令输出；`artifacts/m1f/recovery_content_check.json` | 90d |"
)
s = s[:idx] + new_ev + s[end:]

gate = "| M1-f | 2026-10-01 | 真实库未被触碰 + 全量回归 | `data/growth.db` | 通过 | EV-040 | — |"
assert s.count(gate) == 1, "gate 行未匹配"
s = s.replace(gate, gate + "\n| M1-f | 2026-10-01 | **内容级**恢复（逐行 payload 哈希，非仅计数） | `artifacts/m1f/` | 通过 | EV-041 | — |")

rec_tail = "| 2026-10-01 | M1-f（damage selftest：伪造数据发现与恢复） | EV-037 EV-038 EV-039 EV-040 | 通过 | 上游两项建议（partial 渲染、caught 样本截断） | **M1-f 验收通过** |"
assert s.count(rec_tail) == 1, "验收记录行未匹配"
s = s.replace(rec_tail, rec_tail.replace("EV-040 |", "EV-040 EV-041 |"))

p.write_text(s, encoding="utf-8")
print("PROJECT_ACCEPTANCE 已更新（EV-041、测试数 8→10）")

p = pathlib.Path(".project-to-act/PROJECT_PROGRESS.md")
s = p.read_text(encoding="utf-8")
old_ids = "| EV-037…EV-040 | 2026-10-01 |"
assert s.count(old_ids) == 1, "证据 ID 未匹配"
s = s.replace(old_ids, "| EV-037…EV-041 | 2026-10-01 |")

old_tail = "⑥ 全程在真实库副本上做，逐表确认真实库零差异"
assert s.count(old_tail) == 1, "收尾句未匹配"
s = s.replace(
    old_tail,
    "⑥ 全程在真实库副本上做，逐表确认真实库零差异；"
    "⑦ 事后按用户规格把" + OPEN + "真实 evidence 不变" + CLOSE + "从**计数级加固到内容级**"
    "（逐行 payload 哈希，补上计数级验不出" + OPEN + "条数不变但内容被改写" + CLOSE + "的盲区）",
)
p.write_text(s, encoding="utf-8")
print("PROJECT_PROGRESS 已更新")
