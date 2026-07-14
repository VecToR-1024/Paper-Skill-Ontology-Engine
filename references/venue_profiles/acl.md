# ACL (Annual Meeting of the Association for Computational Linguistics)

- **类型**：会议（NLP 顶会）
- **领域**：自然语言处理

## 篇幅结构

| 项 | 说明 |
|----|------|
| 正文限制 | 8 页（含参考文献） |
| 附录 | 无限制（附录不保证被审稿人阅读） |
| 结构 | 标准 IMRaD + Limitations 必写 |
| 摘要 | ≤ 200 词 |
| 典型长度 | 正文 2500-3500 词 |

**结构惯例**：
- Introduction（含 CARS 三段式）→ Related Work → Method → Experimental Setup → Results → Analysis/Ablation → Limitations → Conclusion
- Limitations 是 ACL 硬性要求（2023 起），缺失会被审稿人标记
- Ethics Statement 建议包含（涉及数据/模型的论文必写）

## 表达偏好

| 维度 | 偏好 |
|------|------|
| 人称 | "we"，不用 "the authors" |
| 语态 | 主动优先，结果部分适量被动可接受 |
| 标题 | 信息型为主，常见："Method for Task" 或 "Verb-ing X with Y" |
| 时态 | 方法→过去时，发现→现在时 |
| 术语 | 需在首次出现时定义，NLP 领域通用术语（BERT, LLM）除外 |
| 风格 | 简洁、直接、可复现性优先。避免过度修辞 |

## 红线（Desk Reject 常见原因）

1. **overclaim**：宣称 SOTA 但实验不充分（如只跑了一个种子）
2. **贡献不足**：纯应用某方法到新任务，无方法论创新或深刻分析
3. **实验薄弱**：缺少消融实验、缺少统计显著性检验、baseline 选择不当
4. **不可复现**：缺少关键实现细节
5. **Related Work 不全**：遗漏近 2 年重要相关工作
6. **Limitations 敷衍**：只写 "more experiments needed" 而不给具体局限分析

## 标题风格

- **主导模式**：信息型标题（占 ~70%）
  - "Method for Task" — eg. "Attention-Based Models for Text Classification"
  - "Verb-ing X with Y" — eg. "Improving Machine Translation with Curriculum Learning"
- **可接受的变体**：
  - 发现型标题 — eg. "Pre-training Causes Overfitting in Low-Resource NMT"
  - 方法命名型 — 仅当方法名足够信息量时（如 "BERT: Pre-training of Deep Bidirectional Transformers"）
- **禁止**："A Study of..." "Research on..." "An Investigation of..." 等空转标题
