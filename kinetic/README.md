# Kinetic Layer v0.1

Kinetic Layer 定义“论文项目世界如何发生变化”。

它不负责语义判断本身。LLM expert 可以提出建议，但真正写入系统的变化必须表现为结构化 action event，并经过脚本校验。

## 文件

```text
event_schema.yml  # event log 统一 envelope
actions.yml       # 允许的 action_type
functions.yml     # 负责校验、追加、投影的确定性函数/工作流
```

## 核心原则

- Event Log 是 append-only。
- 每条 event 必须有单调递增的 `offset`。
- 每条 event 必须引用一个已定义的 `action_type`。
- action 必须引用 Semantic Layer 中已有的 object type 或 link type。
- expert 不直接修改 state；expert 产出 action event proposal，脚本校验后追加到 event log。
- `paper.yml` 等状态文件是 event log 的 projection，不是事实源。

