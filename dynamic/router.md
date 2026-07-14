# Router Policy v0.2

Router 是 context-wise LLM 判断层，不承担 expert 的具体工作。它读取用户请求、项目状态摘要、可用 workflows、expert registry、invocation policy，然后输出结构化 route decision。

Router 不应做机械关键词匹配。关键词只能作为弱线索，不能压过上下文、项目阶段、用户意图和当前 state。

## 触发边界

Suite 一旦触发，就默认处于论文项目语境。

普通句子润色、泛泛写作建议、纯概念问答不进入本 suite；这些由原生 LLM 直接完成。进入 suite 后，不再设计单独“轻量模式”或“exploration 模式”。

## 路由原则

1. 先判断是否已有或需要创建 project state。
2. 根据上下文选择 workflow，而不是根据单个触发词选择 expert。
3. 单 expert 正式执行默认 `isolated_worker`。
4. review / cold-read / independent critique 默认 `multi_agent_review`。
5. router 只输出 route decision，不直接修改 state，不追加 event。
6. route decision 必须声明 allowed actions，缩小本轮 action surface。
7. 信息不足时，优先选择能创建 blocking issue / request human input 的 workflow，而不是硬猜事实。

## Context Signals

Router 应综合判断：

- 用户显式目标：写作、定位、检查、投稿、回应审稿、组装。
- 当前 paper stage：idea、drafting、revision、submission。
- 当前 artifacts：manuscript、venue_card、reviewer_comments、review_report、rebuttal_plan。
- 当前 issues：是否存在 unresolved P0/P1。
- 用户要求输出：正文、报告、proposal、worker packet、最终 artifact。
- 风险等级：是否涉及 claim、venue、submission、review response 等 human gate。

## Workflow Capability Map

```text
paper_intake
  用于创建或导入项目状态。

document_intake
  用于把 PDF/DOCX/image 等原始文档规范化成可审计 artifacts。
  原始 PDF 不应由 writing/review/style 等 expert 直接自由解析；先抽取为 extracted_text_md / extraction_report，再进入后续 workflow。

positioning
  用于 gap、contribution、competition、claim strength、evidence threshold。

argument_extraction
  用于从 Section / Artifact 中抽取 Claim、Evidence、ReasoningStep、Result 和 support links。
  当用户要求“拆论据”“提取论证链”“把论文变成 object graph”时优先选择它，而不是直接进入 mock_review。

writing_revision
  用于根据 state / issue / positioning / venue constraints 和已抽取的 argument graph 写正文或改正文。

style_check
  用于 prose、结构、规则、claim wording、机械写作风险检查；它消费 argument graph，但不负责首次批量抽取。

venue_fit
  用于 venue profile、投稿约束、受众匹配、格式或定位适配。

mock_review
  用于独立冷读、模拟审稿、claim-evidence audit、reject risk；若缺少 Claim / Evidence / ReasoningStep graph，先走 argument_extraction。

rebuttal
  用于 reviewer comments、response strategy、rebuttal plan、response letter。

manuscript_assembly
  用于 artifact 组装、LaTeX/PDF、submission readiness gate。
```

## Conflict Handling

- 写作与检查同时出现：先产生 issue，再让 writing 修订。
- venue 与写作同时出现：先 venue_fit 产生约束，再 writing 修订。
- rebuttal 与正文修改同时出现：先 rebuttal 产生 comment-level decisions，再 writing 修订。
- 最终提交相关请求：必须检查 unresolved P0 issue 和 approval gates。
- 用户提供 raw PDF/DOCX/image 且要求进入论文项目：先选择 document_intake；若抽取失败或不完整，创建 extraction_risk issue，再请求用户提供 Markdown/TeX 或安装 extractor。
- 用户要求 review / style check / writing revision，但 state 只有 Section / Artifact、缺少 Claim / Evidence / ReasoningStep graph：先选择 argument_extraction；之后再进入 review、style 或 writing。

## Output

Router 输出必须遵循 `dynamic/route_decision_contract.md`。脚本只校验该 decision 是否引用了存在的 workflow、expert、invocation mode 和 action types；不靠关键词替 LLM 做路由。
