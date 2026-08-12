# Research Paper Suite

**中文** | [English](README_EN.md)

Research Paper Suite 是一套面向科研论文全生命周期的可审计工作流系统。它以结构化 ontology、append-only event log、确定性校验和 expert orchestration 为核心，将论文中的对象、来源、修改与审批组织为可验证、可回放、可交接的研究状态。

- 当前版本：`0.2.2`
- 开源协议：[Apache License 2.0](LICENSE)

```text
LLM experts 负责语义判断和写作判断
        ↓
proposals.yml 描述建议的状态变更
        ↓
确定性脚本校验引用、策略和人类审批
        ↓
event_log.yml 追加已接受的事件
        ↓
paper.yml 投影当前状态
        ↓
acceptance、handoff 和 visualization 提供交付检查
```

## 产品定位

传统科研写作 agent 往往把大量上下文、规则和中间产物留在聊天记录里。它可以生成不错的文本，但很难稳定回答下面这些问题：

- 这条 Claim 来自哪里？
- Evidence 是否真的锚定到原文？
- 某篇文献只是搜索候选，还是已经核验并用于论证？
- 哪个 expert 提出了修改，谁批准了它？
- 当前 `paper.yml` 能否从历史记录完整重建？
- 换一个 agent 或平台后，工作状态还能否继续？

Research Paper Suite 把这些问题转化为显式的对象、关系、事件和门禁，让研究流程能够跨会话、跨 agent 和跨平台持续推进，并保持完整的来源与决策记录。

## 产品原则

- **结构化状态优先**：论文对象、关系和决策进入可校验状态，而不是只留在对话上下文中。
- **Proposal 驱动**：expert 提交结构化建议，正式状态只由确定性脚本校验和提交。
- **Event log 作为事实源**：`paper.yml` 是可重建投影，历史事件保持 append-only。
- **来源可追溯**：Evidence、Citation 和生成产物必须连接到可审计来源。
- **关键决策由人负责**：主张、证据、投稿和 rebuttal 等高影响动作通过显式人类闸门。

## 五分钟了解工作流

一个已有 PDF 论文的典型流程如下：

```text
PDF / TeX / Markdown
  -> 受控 intake
  -> Artifact + Extraction + SourceSpan
  -> expert invocation packet
  -> report.md + proposals.yml
  -> dry-run validation
  -> human approval when required
  -> append-only events
  -> projected paper state
  -> literature / provenance / issue checks
  -> handoff + static visualization
```

这里有三个关键约束：

1. Expert 只能提交 proposal，不能直接修改正式状态。
2. Event log 是事实源，`paper.yml` 只是可以重新生成的当前投影。
3. 主张、投稿、rebuttal、checkpoint 等高影响操作必须经过人类闸门。

## 快速开始

下面的 `python` 表示你为该项目准备的 Python 解释器。

### 1. 验证安装

```powershell
python scripts/validate_layers.py
python scripts/check_repository_hygiene.py .
python -m pytest -q
```

### 2. 创建项目

从零开始：

```powershell
python scripts/create_empty_project.py work/my-paper `
  --paper-id P-my-paper `
  --title "My Paper" `
  --stage idea `
  --reset
```

从 PDF 开始：

```powershell
python scripts/ingest_pdf_project.py paper.pdf `
  --out-dir work/my-paper `
  --paper-id P-my-paper `
  --title "My Paper"
```

也可以使用 `scripts/ingest_paper_project.py` 导入 TeX、Markdown 或论文目录。

### 3. 校验并提交 proposal

先 dry-run：

```powershell
python scripts/apply_action_proposals.py work/my-paper proposals.yml --dry-run
```

通过后再正式提交：

```powershell
python scripts/apply_action_proposals.py work/my-paper proposals.yml
```

需要人类批准的 action 必须显式记录批准者：

```powershell
python scripts/apply_action_proposals.py work/my-paper proposals.yml `
  --approved-by user `
  --approval-summary "Approved after reviewing the proposed claim changes."
```

### 4. 查看静态可视化

```powershell
python scripts/export_project_visualization.py work/my-paper
```

输出位于：

```text
work/my-paper/visualization/index.html
```

### 5. 正式交付

```powershell
python scripts/handoff_project.py work/my-paper
```

这个命令会运行项目验收、生成 `handoff_manifest.yml`、导出 canonical visualization，并记录关键输出的 hash。

## 静态可视化

`visualization/index.html` 是项目的标准可读视图，不需要 Web 服务即可打开。

| 页面 | 展示内容 |
|---|---|
| Overview | 事件、对象、开放问题、文献覆盖、provenance 和 isolation 摘要 |
| Graph | 对象关系和每个对象的直接事件历史 |
| Timeline | 已接受事件的顺序、actor、function 和影响对象 |
| Issues | 当前问题与 resolved / rejected / wont_fix 历史 |
| Evidence & Files | 文献核验、四类定位覆盖、Evidence -> SourceSpan -> Artifact 链和文件产物 |
| Audit | expert requested mode、actual backend、isolation 状态和 action/function inventory |

导出器同时生成机器可读数据：

```text
visualization.json
story.json
events.json
objects.json
graph.json
literature.json
provenance.json
expert_executions.json
```

正式 handoff 后手动重导页面时，可以要求项目必须已经通过验收：

```powershell
python scripts/export_project_visualization.py work/my-paper --require-accepted
```

## 核心概念

| 概念 | 含义 |
|---|---|
| Object | 论文世界中的语义实体，例如 Claim、Evidence、Citation、Issue |
| Artifact | 对真实文件或生成输出的记录，例如 PDF、提取文本、审稿报告、BibTeX |
| SourceSpan | Artifact 中可复查的具体文本范围，带 locator 和 text hash |
| Link | 对象之间的显式关系，例如 Claim 使用 Evidence |
| Action type | agent 提议的业务级变更，例如 `claim.created` |
| Function | 脚本实际执行的确定性能力，例如 `create_object` |
| Proposal | 尚未提交的结构化变更建议 |
| Event | 已校验并接受的 append-only 事实记录 |
| Projection | 从 event log 回放得到的当前 `paper.yml` |
| Human gate | 对高影响操作的显式人工批准 |

一个常见误区是混淆 Object 和 Artifact：Claim 是语义对象，包含论文草稿的 `.tex` 文件则是 Artifact。长文本通常应保存在 Artifact 中，而不是塞进 event payload 或普通对象字段。

## 三层架构

### Semantic Layer

定义论文世界里“有什么”：

- `ontology/objects.yml`：对象类型
- `ontology/properties.yml`：字段类型和枚举
- `ontology/links.yml`：对象关系
- `ontology/constraints.yml`：跨对象约束

当前主要对象包括：

```text
Core:        Paper, Section, Artifact, SourceSpan, Extraction
Literature:  SearchRun, ExternalWork, SearchResult, Citation
Argument:    Claim, Evidence, ReasoningStep
Experiment:  Method, Dataset, Experiment, Metric, Result
Review:      Review, Issue, Decision
Context:     Venue
```

### Kinetic Layer

定义论文世界“如何变化”：

- `kinetic/actions.yml`：允许的 action type
- `kinetic/functions.yml`：确定性 runtime function
- `kinetic/event_schema.yml`：统一 event envelope

`action_type` 表示业务意图，`function` 表示实际执行方式。每个 action 声明默认 function 和允许的 function，event 则记录真正使用的 function。

### Dynamic Layer

定义 agent “如何工作”：

- `dynamic/router.md`：上下文路由规则
- `dynamic/routing_policy.yml`：route decision 校验策略
- `dynamic/experts.yml`：expert registry
- `dynamic/workflows.yml`：workflow registry
- `dynamic/action_policy.yml`：proposal 证据负担
- `dynamic/approval_policy.yml`：human gate
- `dynamic/invocation_policy.yml`：worker 调用模式

Router 负责理解用户意图，脚本只负责验证结构化 route decision。脚本不会假装通过关键词理解研究目标。

## 主要 Workflows

| Workflow | 用途 |
|---|---|
| `paper_intake` | 创建最小论文项目 |
| `document_intake` | 把 PDF / TeX / Markdown 规范化为 Artifact、Extraction 和 SourceSpan |
| `literature_intake` | 搜索或导入 ExternalWork 候选及 provider metadata |
| `literature_selection` | 核验候选，创建 Citation，分配 positioning role 并连接 Claim / Evidence / Issue |
| `argument_extraction` | 抽取 Claim、Evidence、ReasoningStep、Result 和支持关系 |
| `positioning` | 判断 gap、贡献坐标、竞争关系和 claim strength |
| `writing_revision` | 根据 state、Issue、venue constraints 修订正文 |
| `style_check` | 检查表达、结构和机械写作风险 |
| `venue_fit` | 匹配投稿场所、受众和格式约束 |
| `mock_review` | 运行独立 reviewer packets 并聚合 reject risk |
| `rebuttal` | 映射审稿意见、证据和回复策略 |
| `manuscript_assembly` | 组装稿件并运行 submission readiness gate |

## 可信性门禁

### 来源与 Evidence

可审计的间接来源链是：

```text
Evidence -> SourceSpan -> Artifact
```

SourceSpan 保存 locator、excerpt 和 text hash。Expert 负责判断某段文本是否支持某条 Evidence，脚本负责检查引用对象是否真实存在、链是否完整。

### 文献核验

- `title_only` 和 `bibliographic` ExternalWork 只是候选线索。
- 对应 Citation 必须保持 `tentative`，不能进入 Claim / Evidence 支持链。
- `verified` Citation 必须拥有可审计的 abstract 或 full-text metadata。
- Literature selection 应覆盖 predecessor、direct competitor、later extension、limitation。
- 缺少某类文献时，必须创建带明确 target 和 `missing_literature_role` 的 `citation_gap` Issue。

### Expert 隔离

Invocation packet 只说明请求了什么执行模式，不证明隔离真的发生。实际运行后必须记录：

```text
requested_mode
actual backend
isolation_verified
recorded_by
reason
```

`current_agent_fallback` 不得冒充 isolated worker。

### 人类审批

以下操作默认需要人类确认：

- 改变主 Claim 或贡献坐标
- 选择或更换目标 venue
- 创建新的实验或证据主张
- 忽略 P0 Issue
- 拒绝 reviewer 请求
- 创建 checkpoint
- 确认最终投稿 readiness

### Secret 边界

API key、provider token 和个人联系信息属于运行时配置，不属于论文项目状态。不要把 secret 写入：

```text
event log
paper.yml
proposals.yml
Artifact 内容
handoff manifest
visualization JSON
Git
```

项目状态只保存 `secret_ref` 或不敏感的 provider metadata。详细规则见 `references/backend_secret_management.md`。

## 常用命令

### 状态与事件

```powershell
python scripts/event_log.py validate-log <project>/events/event_log.yml
python scripts/event_log.py project <project>/events/event_log.yml <project>/state/paper-replayed.yml
python scripts/checkpoint_event_log.py list <project>
python scripts/propose_event_revert.py <project> <event-id> --out revert-proposal.yml
```

### 文档和文献

```powershell
python scripts/extract_source_spans.py <project> <artifact-id> --out source-spans.yml
python scripts/fetch_search_results.py semantic_scholar "query" --limit 20 --out results.yml
python scripts/import_search_results.py <project> results.yml --out literature-intake.yml
python scripts/import_work_metadata.py <project> <external-work-id> metadata.yml --out metadata-proposals.yml
python scripts/validate_literature_coverage.py <project>
```

### Expert 和 Review

```powershell
python scripts/validate_route_decision.py route_decision.yml
python scripts/prepare_expert_invocation.py <project> writing_expert --task "Revise the abstract."
python scripts/record_expert_execution.py <invocation-dir> --backend isolated_worker --recorded-by runtime
python scripts/prepare_review_run.py <project> --review-id RV-001 --runner-backend manual_packets
python scripts/aggregate_review_reports.py <project>/reviews/RV-001
```

### 输出与交付

```powershell
python scripts/export_tex_from_state.py <project> --append-event
python scripts/export_bib_from_state.py <project> --append-event
python scripts/validate_project_acceptance.py <project>
python scripts/handoff_project.py <project>
python scripts/export_project_visualization.py <project>
```

完整运行规则见 [SKILL.md](SKILL.md)，开发和修改约束见 [AGENTS.md](AGENTS.md)。

## 目录概览

```text
SKILL.md                 agent 平台入口和运行规则
AGENTS.md                开发者与 coding agent 约束
skill_manifest.yml       包版本、安装模式和必需文件

ontology/                Semantic Layer
kinetic/                 Kinetic Layer
dynamic/                 Dynamic Layer、experts、workflows、templates
references/              secret、venue、style、review、assembly 参考材料
scripts/                 校验、投影、导入、expert、review、导出、handoff 工具
tests/                   单元测试、回归测试和端到端测试
```

## 安装与升级

不要把新 zip 直接合并到已有 skill 目录。`cp -r` 或 `Copy-Item` 可能保留旧文件，形成新旧 schema 和脚本混装。

使用 manifest 驱动的安装器：

```powershell
python scripts/install_skill.py <target_skill_dir>
python scripts/install_skill.py <target_skill_dir> --replace
```

默认模式在目标目录已存在时拒绝安装。`--replace` 会先创建时间戳备份，再用通过 `skill_manifest.yml` 校验的完整 staging copy 替换目标目录。

## 运行保证

Research Paper Suite 通过以下机制保持研究状态的一致性与可审计性：

- append-only event log 保留完整变更历史
- projection replay 可重建当前 `paper.yml`
- proposal dry-run 在提交前校验 schema、引用、策略与审批
- SourceSpan 与 Artifact 提供可复查的来源链
- acceptance 与 handoff 检查交付完整性
- expert execution record 区分请求模式、实际 backend 与隔离状态

## 发布检查

提交或发布前运行：

```powershell
python scripts/validate_layers.py
python scripts/check_repository_hygiene.py .
python -m pytest -q
```

仓库卫生检查会拒绝个人 home 目录、结构化绝对路径、指定姓名、私钥头和常见高置信 API token。需要额外屏蔽某个姓名或机器标识时，可重复使用 `--forbidden-name` 参数。
