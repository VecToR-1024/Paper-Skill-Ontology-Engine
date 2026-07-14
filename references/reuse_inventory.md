# Reuse Inventory v0.1

本文件记录已挖掘到、值得继续复用的资源。正式 expert prompt 不应引用历史来源；这里仅作为开发笔记和迁移清单。

## 已接入

- `references/venue_profiles/`: 12 个 cached venue profiles，覆盖 NLP / ML / CV / Nature Machine Intelligence。用于 venue_expert 的默认受众画像和风险提示。
- `scripts/reused/quick_scan.py`: 机械写作预扫，可继续由 style workflow 调用。
- `scripts/reused/semantic_scholar.py`: 论文搜索封装，可继续作为 positioning / citation gap 的候选工具。
- `scripts/reused/check_consistency.py`: 具体实现未必直接适配，但“用配置检查 prompt / rule / trigger 一致性”的思路值得保留。

## 已暂存，待后续拆分

- `references/style_rules/rules.md`: 完整 style rules 暂存版。后续可拆成 style_expert 按需加载的 rule subsets。
- `references/output_templates/output_templates.md`: 完整 output templates 暂存版。后续可继续拆成 `dynamic/templates/`。
- `references/review/reviewer_roles.md`: review 三角色清单，供 review_expert / multi-agent workflow 使用。
- `references/assembly/latex_pdf_rules.md`: LaTeX / PDF 组装规则，供 assembly_expert 使用。
- `dynamic/templates/pre_submission_checklist.md`: 投稿前检查清单模板。
- `dynamic/templates/response_letter.md`: 审稿回复模板。
- `dynamic/templates/rebuttal_plan.md`: 审稿回复策略模板。
- `dynamic/templates/stage_exit_report.md`: 阶段出口汇报模板。
- `dynamic/templates/async_summary_report.md`: 异步汇总报告模板。
- `dynamic/templates/manuscript_assembly_output.md`: 稿件组装输出模板。
- `dynamic/templates/title_candidates.md`: 标题候选模板。

## 使用原则

- 能被脚本稳定读取的内容放 reference / template / script。
- 会过期的 venue 细节只能作为 cached prior；真实投稿前必须校验当年官方 guideline。
- 不把历史迁移过程写进 expert prompt；expert 只看到当前 suite 的自洽资源。
