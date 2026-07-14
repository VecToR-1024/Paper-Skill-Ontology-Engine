# Dynamic Layer v0.1

Dynamic Layer 定义“运行时如何让系统活起来”。

它位于 Semantic 和 Kinetic 之上：

- Semantic Layer 定义对象和关系。
- Kinetic Layer 定义 action/event/function。
- Dynamic Layer 定义 router、expert、workflow、action policy、approval policy。

本层不是全硬配置。`experts.yml`、`workflows.yml`、`action_policy.yml`、`approval_policy.yml` 是半硬配置，脚本可以校验引用；`router.md` 和 `experts/*.md` 是 LLM 可读策略文档。

## 当前原则

- 单 skill suite + 多 expert 文件。
- multi-agent 只优先用于 review 场景。
- router 保持薄，不内嵌所有 expert 细节。
- expert 不直接改 state，只提出 action event proposal。
- 高影响 proposal 必须写明 rationale、references 和审批状态，由 `apply_action_proposals.py` 做硬校验。
- 所有 state change 进入 Event Log。
- 高风险科研判断和投稿策略需要人类确认。
