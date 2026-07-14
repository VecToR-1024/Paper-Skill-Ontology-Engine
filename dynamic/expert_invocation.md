# Expert Invocation Policy v0.1

## Core Problem

在单一长会话 agent 内加载 expert brief，无法真正主动卸载。只要 brief 进入上下文，它就会继续占用 token，并可能影响后续判断。

因此 “single skill + multiple experts” 不应理解为主 agent 逐个读取所有 expert 文件，而应理解为：

```text
single suite skill provides ontology / actions / scripts
expert files are invocation packets
main agent orchestrates, freezes input, receives proposals, and commits events
```

## Invocation Modes

### 1. Isolated Expert Worker

主 agent 生成一个冻结的 invocation packet，新 worker 只读取该 packet、对应 expert brief、必要 state/artifact，并输出 report / proposals。worker 不直接写 event log。

适用：

- 正式执行 positioning / writing / style / venue / rebuttal / assembly。
- 需要保护主 agent 上下文轻量。
- 需要复现一次 expert 调用的输入输出。
- 需要让 proposal 进入统一 event-log 提交流程。

默认单 expert 执行应使用 isolated expert worker。

### 2. Multi-Agent Review

多个 isolated workers 并行或分批运行，每个 worker 拿到不同 role packet，彼此隔离。AC / aggregator 读取它们的输出，生成最终 proposals。

适用：

- mock review。
- independent cold-read。
- adversarial check。
- 需要避免 reviewer 互相影响的场景。

## Runtime Rules

- Suite 一旦触发，就默认处于论文项目语境；普通轻量聊天不进入本 suite。
- Expert worker 不能修改 `paper.yml`。
- Expert worker 不能追加 `event_log.yml`。
- Expert worker 只能输出 `proposals.yml`、report artifact 或 role findings。
- 主 agent / runtime 负责校验 proposals、分配 offset、append event、project state。
- `prepare_expert_invocation.py` 只记录 requested mode，不证明 worker 已被隔离执行。实际执行后必须用 `record_expert_execution.py` 记录 backend；fallback 还必须写 reason。
- Event Log 是唯一状态提交层；worker 输出不是事实，只有被校验并提交后的 event 才是事实。
- 长文本必须作为 Artifact 文件管理，不塞进 event payload。
- 主 agent 完成提交或导出后，必须给用户一个简短、可读的 completion note：本轮改了什么、这对论文状态意味着什么、还剩哪些 open issue / human gate、产物在哪里。不要只返回文件卡片或脚本状态。

## Default Decision

```text
single-expert execution
  -> isolated_expert_worker

review / cold-read / independent critique
  -> multi_agent_review
```

不把 inline expert loading 作为正式运行模式。它会污染主 agent 长上下文，违背 prompt 轻量化目标。

## Execution Record

生成 invocation packet 后，runner manifest 中的 `execution.backend` 初始为 `unassigned`，`isolation_verified` 为 `false`。执行完成后必须记录实际 backend：

```powershell
python scripts/record_expert_execution.py <invocation_dir> --backend isolated_worker --recorded-by <runtime>
```

若平台没有隔离 worker，只能由 current agent 执行，则必须如实记录 fallback，不能在 report 中把它称为 isolated worker：

```powershell
python scripts/record_expert_execution.py <invocation_dir> --backend current_agent_fallback --recorded-by <runtime> --reason "Platform worker isolation unavailable."
```

`current_agent_fallback` 和 `manual_packet` 都不构成已验证的上下文隔离。Project acceptance 和 handoff manifest 会保留这项审计信息并给出 warning。

## Why Event Log Still Matters

即使最终只有一个主 agent 提交 event，event log 仍然有意义：

- 它把多个 isolated expert 的输出合并成一个线性、可审计的事实序列。
- 它避免 worker 直接抢写 state。
- 它让 checkpoint / restore / replay 成为可能。
- 它让长期论文项目不依赖聊天上下文记忆。
