# NeurIPS (Conference on Neural Information Processing Systems)

- **类型**：会议（ML 顶会）
- **领域**：机器学习

## 篇幅结构

| 项 | 说明 |
|----|------|
| 正文限制 | 9 页（含参考文献） |
| 附录 | 无限制（附录不保证被审稿人阅读） |
| 结构 | IMRaD + Broader Impact |
| 摘要 | 无硬性词数限制，建议 ≤ 200 词 |

**结构惯例**：
- Introduction → Related Work → Method → Experiments → Discussion → Broader Impact
- 实验部分特别重要——NeurIPS 审稿人期望：
  - 多数据集/多任务验证
  - 消融实验（每个设计选择都要 justify）
  - 与 ≥ 3 个 strong baseline 对比
- Broader Impact Statement 是 NeurIPS 特色要求（2020 起）

## 表达偏好

| 维度 | 偏好 |
|------|------|
| 人称 | "we" |
| 语态 | 主动优先 |
| 标题 | 偏方法名+效果型，常见："Method Name: What It Achieves" |
| 时态 | 方法→过去时，定理/性质→现在时 |
| 风格 | 精确、实验驱动、可复现。数学表达（定理/证明）在正文中需简洁，完整证明放附录 |

## 红线（Desk Reject 常见原因）

1. **实验不足**：NeurIPS 审稿人对实验要求极高——单数据集、无统计检验、无消融 → 直接拒
2. **overclaim**：声称 SOTA 但 baselines 没调参
3. **novelty 不足**：纯组合现有方法无独特洞察
4. **related work 遗漏**：特别是近 1 年 NeurIPS/ICML/ICLR 上的相关工作
5. **Broader Impact 缺失或敷衍**

## 标题风格

- **主导模式**：方法驱动型（占 ~60%）
  - "Method Name: What It Achieves" — eg. "Attention Is All You Need"
  - "Verb-ing X via Y" — eg. "Training GANs via Dual Averaging"
- **可接受**：
  - 发现型标题 — eg. "Deep Double Descent: Where Bigger Models Hurt"
  - 方法论型 — 纯方法命名只有当方法名本身已是贡献时才接受
- **禁止**：空转标题、过长的描述型标题
