# Route Decision Contract v0.1

Router 输出一个 YAML decision。它是 LLM 的 context-wise 判断结果，之后由脚本校验结构和引用。

## Shape

```yaml
route_decision:
  route_id: RD-example
  suite_triggered: true
  project_required: true
  workflow: writing_revision
  primary_expert: writing_expert
  invocation_mode: isolated_worker
  secondary_experts:
    - style_expert
  allowed_actions:
    - section.upserted
    - issue.created
    - artifact.created
  state_reads:
    - Paper
    - Section
    - Claim
    - Issue
  artifact_reads:
    - A-positioning-card
  human_gates:
    - claim.updated
  rationale: "The user asks to revise a manuscript section using existing project context."
  next_step:
    type: prepare_expert_invocation
    task: "Revise the abstract using the current paper state and produce proposals only."
```

## Rules

- `suite_triggered` 为 false 时，不应调用 expert 或 workflow。
- `workflow` 必须存在于 `dynamic/workflows.yml`。
- `primary_expert` 和 `secondary_experts` 必须存在于 `dynamic/experts.yml`。
- 对于 `experts: []` 的确定性 workflow（例如 `document_intake`），`primary_expert: null` 且 `invocation_mode: null` 合法。
- `invocation_mode` 必须存在于 `dynamic/invocation_policy.yml`，除非该 workflow 是 expertless deterministic workflow。
- `allowed_actions` 必须是 workflow 与 expert 都允许的 action 子集。
- 对于 expertless deterministic workflow，`allowed_actions` 必须是 workflow action surface 的子集。
- `rationale` 必须引用上下文判断，不写关键词匹配理由。
- `next_step.type` 只能是 runtime 已知动作，例如 `prepare_expert_invocation`、`prepare_review_run`、`direct_answer`、`request_user_input`。

## Expertless Document Intake

Raw PDF/DOCX/image 输入应先走确定性的 document intake，而不是让 writing/review/style expert 直接解析原始文件：

```yaml
route_decision:
  route_id: RD-document-intake
  suite_triggered: true
  project_required: true
  workflow: document_intake
  primary_expert: null
  invocation_mode: null
  allowed_actions:
    - paper.created
    - artifact.created
    - extraction.created
    - issue.created
  rationale: "The user provided a raw PDF that must be normalized into auditable artifacts before expert review."
  next_step:
    type: run_document_intake
    task: "Run scripts/ingest_pdf_project.py, then inspect extraction_report before routing to review or writing."
```

## Argument Extraction Route

当用户要求“拆论据”“提取论证链”“把论文变成 object graph”，或后续 review / style / writing 需要结构化论证图但 state 尚未具备时，优先选择 `argument_extraction`：

```yaml
route_decision:
  route_id: RD-argument-extraction
  suite_triggered: true
  project_required: true
  workflow: argument_extraction
  primary_expert: positioning_expert
  invocation_mode: isolated_worker
  allowed_actions:
    - claim.created
    - evidence.created
    - reasoning_step.created
    - issue.created
    - link.created
  state_reads:
    - Paper
    - Section
    - Claim
    - Evidence
    - ReasoningStep
    - Issue
  artifact_reads: []
  human_gates: []
  rationale: "The user wants the manuscript decomposed into semantic argument objects before review or revision."
  next_step:
    type: prepare_expert_invocation
    task: "Use dynamic/templates/argument_extraction.md and output proposals only."
```

## Negative Route

不进入 suite 时：

```yaml
route_decision:
  route_id: RD-direct
  suite_triggered: false
  project_required: false
  workflow: null
  primary_expert: null
  invocation_mode: null
  allowed_actions: []
  rationale: "The request is a general writing question without paper project state or artifact needs."
  next_step:
    type: direct_answer
```
