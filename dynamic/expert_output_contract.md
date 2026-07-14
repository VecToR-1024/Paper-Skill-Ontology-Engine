# Expert Output Contract v0.2

Expert 不直接修改 `paper.yml`。当 expert 需要改变项目状态时，只输出 `proposals:`，由 runtime 脚本转换为 event、校验 schema，并追加到 Event Log。

## 基本格式

```yaml
proposals:
  - action_type: issue.created
    payload:
      issue_id: I-example
      paper_id: P-example
      category: weak_positioning
      severity: P1
      issue_status: open
      evidence: "Abstract states a broad contribution but does not identify the competing baseline."
      suggested_action: "Clarify the nearest baseline and state the exact difference."
      target_object_type: Claim
      target_object_id: C-main-claim
```

## 字段规则

- `action_type` 必填，表示 agent 的业务指令。
- `payload` 必填，必须满足 `kinetic/actions.yml` 对该 action 的字段要求。
- `actor` 可选；缺省由调用方填入当前 expert。
- `function` 可选；缺省由 action 的 `default_function` 推断。expert 只有在明确需要非默认 runtime 函数时才填写。
- `object_type` / `object_id` 通常不要手写，runtime 可从 action config 和 payload 主键推断。
- `references` 可选，用于指向 section、claim、citation、artifact、external_work 或外部证据。
- `approval` 可选，用于记录人工确认状态；需要人类判断的 proposal 应保持 pending，而不是伪装成已批准。Runtime 正式 apply 时会拦截未批准的 approval-required actions；只有 `approval.status: approved` 且包含 `approved_by`，或主 agent 在用户明确批准后使用 `--approved-by`，才可提交。

## Action Rationale

高影响 proposal 必须承担行动理由，而不是只给出一个看似合法的 payload。`dynamic/action_policy.yml` 定义哪些 action 需要 `rationale`、需要哪些字段、至少要引用哪些现有对象或 event。

`rationale` 是 proposal-level 字段，不要塞进 `payload`：

```yaml
action_type: claim.updated
payload:
  claim_id: C-main-claim
  field: content
  value: "..."
references:
  issue_ids:
    - I-needs-evaluation-plan
  claim_ids:
    - C-main-claim
rationale:
  problem_addressed:
    issue_id: I-needs-evaluation-plan
    summary: "The current claim is stronger than the recorded evaluation support."
  why_this_action: "Weakening the claim preserves the paper's direction while avoiding an unsupported result claim."
  expected_state_delta:
    affected_objects:
      - C-main-claim
    summary: "The claim becomes an auditable draft claim rather than a completed empirical finding."
  alternatives_considered:
    - "Create new evidence: rejected because no experiment artifact exists yet."
  risks:
    - "The contribution may read as less mature until evaluation evidence is added."
  confidence: medium
```

当前高影响 action 包括 `claim.updated`、`paper.target_venue_set`、`issue.status_changed`、`issue.severity_changed`、`decision.recorded`、`link.removed`、`checkpoint.created` 和 `submission.finalized`。这些 proposal 还必须显式经过 human gate；expert 只能提出，不能自行批准。

## SourceSpan Anchors

`SourceSpan` 是某个已登记 Artifact 中的短文本定位锚点。它只回答“这条语义对象从哪里来”，不证明“这个来源语义上支持该 claim”。支持关系仍应通过 `claim_supported_by_evidence`、`claim_supported_by_result`、`claim_anchored_to_source_span` 等显式 link 表达。

`claim.created`、`evidence.created`、`result.created` proposal 必须二选一：

```yaml
references:
  source_span_ids:
    - SPAN-example-0001
```

或：

```yaml
rationale:
  unanchored_reason: "This is a user-authored thesis statement, not extracted from a source artifact."
```

`citation.created` 可以使用同样的 `source_span_ids`，也可以引用已经导入的候选文献：

```yaml
references:
  external_work_ids:
    - EW-example
```

随后应创建 `citation_represents_external_work` link，把 Citation 和 ExternalWork 明确连起来。

从 ExternalWork 创建的 Citation 还必须声明 `verification_status`：

- `tentative`: 只有题名或普通书目信息，尚未核对摘要/全文；不得创建 `claim_uses_citation` 或 `evidence_uses_citation`。
- `verified`: 已有可审计的摘要或全文元数据，即 ExternalWork 的 `metadata_quality` 为 `abstract` 或 `full_text`；此时才允许进入 claim/evidence 支持链。

`Citation.positioning_role` 应明确该文献在选择集中的作用：`predecessor`, `direct_competitor`, `later_extension`, `limitation`, `background` 或 `unknown`。这个字段表达文献定位，不等于它必然支持某个 claim。

不要使用自评 `confidence` 来替代 anchor。脚本只校验 source span 是否存在；它不判断该 span 是否真的支持语义主张。

## Issue Targeting

`issue.created` 应优先指向最小的相关语义对象，而不是默认指向整篇 Paper。

```yaml
target_object_type: Claim
target_object_id: C-main-claim
```

允许的 target 类型包括 `Paper`, `Section`, `Claim`, `Evidence`, `ReasoningStep`, `Method`, `Dataset`, `Experiment`, `Metric`, `Result`, `Citation`, `Venue`, `SearchRun`, `ExternalWork`, `SearchResult`, `SourceSpan`, `Extraction`, `Artifact`。只有真正全局的问题才使用 `Paper`。旧字段 `section_id`, `claim_id`, `review_id` 可继续作为上下文或兼容字段；其中 `review_id` 表示来源 review，不表示 issue 的目标对象。

`category: citation_gap` 的 issue 必须同时提供 `target_object_type`、`target_object_id` 和 `missing_literature_role`。缺口必须说明具体影响哪个对象，以及缺的是 predecessor、direct competitor、later extension 还是 limitation 文献，不能只写一个无目标的全局提醒。

## Severity

`severity` 不是所有 proposal 的全局字段，但凡创建 `issue.created`，必须在 `payload` 中填写 `severity`。如果一个 proposal 本质上是在报告风险，也应优先转成 `issue.created`，而不是把风险藏在普通说明里。

当前 severity 取值：

- `P0`: 阻断级问题。不处理会明显改变论文主张、可信度、投稿判断或实验结论。
- `P1`: 高优先级问题。不一定阻断，但会显著削弱定位、论证、证据链或读者理解。
- `P2`: 普通改进项。值得修，但不应打断当前主要工作流。

不要用 severity 表达“我有多不喜欢这段文字”。它只表达对论文目标的影响程度。

## Issue Reclassification

当论文定位、claim strength、证据状态或 human decision 改变，使一个 issue 的当前风险等级不再准确时，使用 `issue.severity_changed`，不要只在报告里解释。

```yaml
action_type: issue.severity_changed
payload:
  issue_id: I-single-case
  previous_severity: P0
  severity: P2
  reclassification_reason: "The paper was repositioned as an exploratory single-case study, so single-case scope is no longer a blocking validity risk."
```

该 action 表示“当前风险等级变了”；历史严重性仍保留在 event log 和 `previous_severity` 中。若问题已经解决，还应单独使用 `issue.status_changed` 把 `issue_status` 改成 `resolved`，让可视化把它放进历史区。

`issue.status_changed` 和 `issue.severity_changed` 都是 approval-required actions。Expert 可以提出 proposal，但不能自行批准；未批准时正式 apply 会失败且不会追加任何 event。

## 行为边界

- 不输出完整 state snapshot。
- 不把大段正文塞进 event；短片段可以放入 `Section.content`，长文本应作为 Artifact 管理。
- 不把完整章节或整篇稿件长期塞进 `Section.content`。短片段可以用 `section.upserted`，长章节、全文草稿、导出的 `.tex` / `.md` / `.html` 必须作为 Artifact 记录，并用 `content_path` 或 artifact link 指向文件。
- 不默认生成项目级 HTML 展示页、dashboard 或“给作者看的漂亮总览页”。默认可视化只使用 `scripts/export_project_visualization.py` 生成的 `visualization/index.html`。
- 只有用户明确要求额外 HTML 预览/展示页时，才可以创建该文件；并且必须同时输出 `artifact.created` proposal 记录路径、类型、生成者和用途。
- 不留下未登记的长期文件。`outputs/report.md` 和 `outputs/proposals.yml` 是 invocation 临时输出；其他需要保留的文件都必须进入 Artifact。
- `Evidence.source_ref` 不能替代来源结构。外部网页、论文、数据、截图、搜索报告等来源必须通过 `artifact_id`、`evidence_uses_citation` / `claim_uses_citation` link 或 `citation_represents_external_work` link 连接到 Artifact / Citation / ExternalWork；`source_ref` 只用于短的定位提示。
- 不把 `[待补充]`、`待引用`、`TODO` 这类占位文本伪装成 Evidence。缺证据时创建 `issue.created`，保持 issue open，直到真实来源被记录并链接。
- 不编造 citation、gap、baseline 或实验结果。不确定时创建 `issue.created`，而不是创建假事实。
- 多个 proposal 应保持原子化：一个 action 只做一件事。

## Argument Extraction

当任务是“拆论据”或“填充 object graph”时，expert 应使用 `dynamic/templates/argument_extraction.md`。输出仍然必须是 `proposals:`，常见顺序是：

1. `claim.created`
2. `evidence.created`
3. `reasoning_step.created`
4. `result.created` / `citation.created` / `method.created` 等可选研究对象
5. `link.created`
6. `issue.created` for missing or weak support

不要把抽取结果只写成 Markdown 表格。表格可以作为思考中间态，但最终交给 runtime 的必须是可校验 proposals。

## Literature Selection

当任务是“从已导入搜索结果中挑引用”时，expert 应使用 `dynamic/templates/literature_selection.md`。该工作流不创建 `ExternalWork` / `SearchRun` / `SearchResult`；它只把已有候选文献转成论文实际引用和关系。

常见顺序是：

1. `citation.created` with `references.external_work_ids`, `verification_status`, and `positioning_role`
2. `link.created` for `citation_represents_external_work`
3. `link.created` for `claim_uses_citation` or `evidence_uses_citation`, but only for verified citations
4. targeted `issue.created` when a candidate is relevant but the paper still needs synthesis, verification, or a better source
5. `validate_literature_coverage.py` to require verified predecessor, direct competitor, later extension, and limitation coverage, or a targeted open citation-gap issue for each missing role

不要把“相关”当成“支持”。如果候选文献只是背景或对比，请用 `Citation.role` 和相应 link 表达；如果是否支持 claim 仍不确定，创建 open Issue。
