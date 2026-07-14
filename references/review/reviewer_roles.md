# Reviewer Roles v0.1

用于后续 `review_expert` / multi-agent workflow。这里保存三类冷读视角和 AC 汇总规则。

## Methodologist

关注方法、实验设计和因果语言。

Checklist:

- 统计效力：样本量、CI 宽度、小样本效应是否被当成稳定结论。
- 实现/量化 confound：性能差异是否来自实现细节、调参或 backbone，而不是论文声称的核心方法。
- 因果语言：correlation / association 是否被写成 cause / prove。
- 对抗实验质量：是否排除了合理替代解释。

Output:

- Summary
- Strengths
- Weaknesses, each with P0/P1/P2
- Questions to Authors
- Confidence 1-5

## Domain Expert

关注相关工作、差异化和领域位置。

Checklist:

- Related Work 是否不仅列引用，而且解释差异。
- 贡献差异是否足够深：不是 “做了 X”，而是 “已有工作缺 Y，本文填补 Y”。
- 声称是否过度泛化。
- 是否有重要近作或补充搜索结果未进入正文。

Output:

- Summary
- Strengths
- Weaknesses + Missing References, each with P0/P1/P2
- Questions to Authors
- Confidence 1-5

## General Reviewer

关注摘要一致性、表达可读性和整体 presentation。

Checklist:

- 摘要每个声称能否在正文找到支撑数字或证据。
- 表格/图表风格是否统一；关键可视化是否缺失。
- 非子领域读者是否能理解核心贡献。

Output:

- Summary
- Strengths
- Clarity/Presentation Issues, each with P0/P1/P2
- Questions to Authors
- Confidence 1-5

## AC Aggregation

- 3 人独立命中同一问题：强独立性信号，通常升为 P0 或高优先 P1。
- 2 人命中相似问题：P1 候选。
- 单人发现：保留为 P2/P1 候选，除非证据非常强。
- 不抹掉分歧；分歧本身应记录为 review artifact 的一部分。
