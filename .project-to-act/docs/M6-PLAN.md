# M6 Memory 边界（v0.1）

M6 先证明记忆可验证地存在，不实现自动摘要、推荐或主动提醒。

已确认顺序：

```text
M6-a 契约与审计
M6-b history 派生 + state projection
M6-c memory → task context
```

M6-a 已实现：

* `MemoryService.remember` 是应用层唯一写入入口；
* profile/state 必须带 `user_statement`、`task`、`gap` 或 `assessment` 来源；
* 相同来源与内容回放得到同一记录；
* 更新保留旧行并写 `memory_changed`；
* history 与能力成就表述在本步拒绝。

M6-b 将删除 state/history 后，由同一来源重建出同一当前视图。
