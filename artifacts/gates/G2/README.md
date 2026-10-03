# G2 · 证据可追溯性门

- 判定：**通过**
- 抽样：5 条 assessment（来自 7 条可追溯评定行 / 共 7 条评定行；确定性遍历）
- 逐跳：assessment → claim → evidence → passage → source，引文逐字（`quote_verbatim`）
- 追溯路径：`supports`（rated 行）/ `capability_bindings`（insufficient_evidence 行）
- 质量门：`audit_store` → pass / 0 violations
- dossier（6 份）：`dossiers/`
- 运行：`artifacts/m4e/run_m4e.py --mode real`（结果见 `result-real.json`）
