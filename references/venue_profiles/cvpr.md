# CVPR (Conference on Computer Vision and Pattern Recognition)

- **类型**：会议（CV 顶会）
- **领域**：计算机视觉

## 篇幅结构

| 项 | 说明 |
|----|------|
| 正文限制 | 8 页（含参考文献） |
| 附录 | 作为 supplementary material 单独提交 |
| 结构 | IMRaD，图密集型 |
| 摘要 | 无硬性词数限制 |

**结构惯例**：
- 图形/可视化是 CVPR 论文的核心——一篇论文通常含 6-10 张图
- Introduction 的第一个图往往是 framework overview——必须一目了然
- Experiments 部分需包含：定量对比表 + 定性可视化 + 消融实验
- Supplementary 视频在 CVPR 常见且被重视

## 表达偏好

| 维度 | 偏好 |
|------|------|
| 人称 | "we" |
| 语态 | 主动优先 |
| 标题 | 任务+方法型，常见："Task via Method" 或 "Method for Task" |
| 风格 | 图驱动的叙事——每张图必须能独立传达核心信息。文字精炼，不冗余 |

## 红线（Desk Reject 常见原因）

1. **实验不足**：只有一个数据集、缺少与最新 SOTA 的对比、缺少消融
2. **novelty 不足**：换 backbone、调参、简单的多任务组合不构成 CVPR 级别的贡献
3. **overclaim**：声称 SOTA 但没有在所有标准 benchmark 上验证
4. **图质量差**：framework overview 图不清晰、定性结果选择性地只展示好 case
5. **Related Work 不全**：CVPR 投稿量极大，遗漏近 1 年的相关工作极易被审稿人发现

## 标题风格

- **主导模式**：任务+方法型（占 ~70%）
  - "Task via Method" — eg. "Object Detection via Region-based CNNs"
  - "Verb-ing Task with Method" — eg. "Segmenting Objects with Attention"
- **可接受**：
  - 方法命名型 — 当方法名简洁且首次提出时
  - 发现型 — eg. "Why Do Self-Supervised Models Learn Useful Representations?"
- **禁止**：空转标题（"A Study of..."）
