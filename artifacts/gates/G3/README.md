# G3 · 能力审计门（A/B 对照 + C 负对照）

- 判定：**通过**
- A（弱证据）：理解 2 / 实践 证据不足（insufficient_evidence）
- B（强证据）：理解 2 / 实践 3（rated）
- C（负对照）：JD → domain_reference（不进入 supports）
- 增强观察：B 实践 ≥3 = True
- 真实运行预算：17 HTTP 请求（上限 17，零额外重试）
- 材料清单（真实 / 构造标注）：`inputs.json`；两轮记录：`rounds.json`；攻击与预算：`attack.json`
