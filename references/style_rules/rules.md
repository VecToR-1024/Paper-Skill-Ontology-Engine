# 科学写作风格规范

> AI 以此规范生成初稿并自检。三阶自修订 R3（措辞审查）逐条对标。
> 每一条规则都是研究评价框架 v2.10 D5.1（表达质量）的评分证据来源。
> 更新历史见末尾变更日志。

---

## L1 · 核心原则（4条）

**这不是品味建议——这是 ANR 写作的精神宪法。** 当两条规则冲突时，回到原则判断。

| # | 原则 | 含义 | 来源 |
|:--:|------|------|------|
| 1 | **清晰是第一义务** | 读者时间是借来的。你的工作不是展示自己多聪明，是让读者毫不费力地理解复杂事物 | Zinsser (1976) |
| 2 | **精确优于流畅** | 如果必须在"表达漂亮"和"表达精确"之间二选一，选精确。一个精确的笨句子比一个漂亮的模糊句子更有价值 | Feynman; Gopen & Swan (1990) |
| 3 | **每个词必须挣到它的位置** | 每句话默认可以缩 20%。删除后意思不变 → 那个词不该存在 | Zinsser; Strunk & White |
| 4 | **诚实呈现不确定性** | 不确定就说不知道。"suggest" 和 "demonstrate" 的距离是科学诚信的距离。永远不假装知道你不知道的事 | Feynman (1974); Hyland (2005) |

---

## L2 · 可执行规则（28条）

### 句法（6条）

---

#### 2.1 主动语态优先

主语做动作，不做动作的承受者。

| | 英文 | 中文 |
|--|------|------|
| **反例** | "It was observed that the temperature increased." | "可以观察到温度出现了上升。" |
| **正例** | "We observed a temperature increase of 3°C." | "我们观察到温度上升了 3°C。" |

**技术报告例外**：失败记录中被动语态可用于保持客观叙述。"The experiment was terminated after 12 hours due to resource exhaustion."

**检查项**：全文被动语态/隐性主语占比 < 30%。

---

#### 2.2 短句

读者每次只能 hold 住一个主张。长句 = 强迫读者在脑中拆句。

| | 英文 | 中文 |
|--|------|------|
| **反例** | "The proposed framework, which builds on the theoretical foundations established by Smith (2020) and extended by Jones (2021), demonstrates a significant improvement over existing approaches when evaluated on the benchmark datasets that have been widely used in the literature." | — |
| **正例** | "Our framework builds on Smith (2020) and Jones (2021). It improves over existing approaches on standard benchmarks." | "我们的框架基于 Smith (2020) 和 Jones (2021) 的工作，在标准基准上优于现有方法。" |

**检查项**：平均句长 15-25 词/字（以英文计），单句上限 35 词/字。一段内 3 句连续长句 → 必须拆一句。

---

#### 2.3 一句一个主张

一个句子只表达一个核心意思。多个主张挤在一句 → 读者丢失线索。

| | 英文 | 中文 |
|--|------|------|
| **反例** | "We propose a novel architecture that reduces latency by 30% while also maintaining accuracy comparable to state-of-the-art methods, and we further show that our approach generalizes across three domains." | — |
| **正例** | "We propose a novel architecture. It reduces latency by 30% while matching state-of-the-art accuracy. Further experiments show generalization across three domains." | — |

**检查项**：含 2+ 个主张的句子 → 拆分成 2+ 句。

---

#### 2.4 动作用动词表达（避免名词化）

名词化 = 把动作伪装成名词。最隐蔽的啰嗦形式。

| | 英文 | 中文 |
|--|------|------|
| **反例** | "The implementation of the optimization of the parameter selection was conducted." | "对参数选择的优化的实施被执行。" |
| **正例** | "We optimized parameter selection." | "我们优化了参数选择。" |

**常见名词化替换表**：

| 名词化 | 替换为 |
|--------|--------|
| "An analysis of X was performed" | "We analyzed X" |
| "The demonstration of the effect was achieved" | "We demonstrated the effect" |
| "A comparison between A and B was made" | "We compared A and B" |

**检查项**：每段名词化（tion/sion/ment/ance 结尾）动词 < 1 个。超过 → 改写为动词。

---

#### 2.5 避免嵌套从句

超过一层的从属从句 = 读者必须回读。

| | 英文 |
|--|------|
| **反例** | "The model that the researchers who were funded by the institute that was established in 2010 developed outperformed all baselines." |
| **正例** | "The model was developed by researchers at an institute founded in 2010. It outperformed all baselines." |

**检查项**：含 2+ 层嵌套从句的句子 → 必须拆。

---

#### 2.6 人称统一

全文只用一种自称方式。混用 = 读者困惑"谁在说话"。

| 文档类型 | 推荐自称 | 理由 |
|---------|---------|------|
| 技术报告 | "我们" / "we" | 记录真实研究过程，人和 AI 都是参与者 |
| 学术论文（中文） | "本文" | 传统学术规范 |
| 学术论文（英文） | "we" | 现代学术写作主流——比 "the authors" 更自然 |
| 开题报告/中期报告 | "本研究" | 面向外部评审，正式度居中 |

**反例**（同一段落内）："我们设计了一个实验……本研究采用了双盲设计……笔者对结果进行了分析。"

**检查项**：全文人称不一致处 → ID + 统一。

---

### 信息结构（4条）

---

#### 3.1 已知信息 → 新信息

每个句子的开头放读者已经知道的东西，末尾放新的信息。大脑在新信息位置分配最多注意力。

| | 英文 |
|--|------|
| **反例** | "The optimal trade-off between latency and accuracy has been a long-standing challenge. Our approach addresses this challenge through hierarchical information decomposition." |
| **正例** | "Balancing latency and accuracy has been a long-standing challenge. We address it through hierarchical information decomposition." |

**规则**：后句的开头接前句末尾的信息。句子链 = 信息流。

**检查项**：相邻两句——后句首词是否与前句末词有语义承接？不承接 → 加过渡。

---

#### 3.2 动词靠近主语

读者读到主语后会下意识找动词。中间塞东西 → 短期记忆过载。

| | 英文 |
|--|------|
| **反例** | "The model, after extensive hyperparameter tuning and cross-validation on multiple datasets that span diverse domains, achieved state-of-the-art results." |
| **正例** | "After extensive tuning and cross-validation on diverse datasets, the model achieved state-of-the-art results." |

**检查项**：主语和动词之间 > 6 个词的英文句 → 调整语序。

---

#### 3.3 压力位置

每句最重要的信息放在句尾——这是句子的"压力位置"，读者在此停顿和整合。

| | 英文 |
|--|------|
| **弱** | "We found a significant improvement of 23%. The improvement came from the attention mechanism." |
| **强** | "We found that the attention mechanism drove a 23% improvement." |

**中文适配**：中文句尾同样是压力位置。"我们发现了 23% 的提升" → "提升源于注意力机制"。

**检查项**：一段内，每句尾词是否承载了该句最重要的信息？不是 → 调整语序。

---

#### 3.4 段落首句即论点

读者扫读时只看每段第一句。如果第一句不能独立传达该段的论点 → 读者不会读剩下的。

| | 英文 |
|--|------|
| **反例**（首句） | "In this section, we discuss several aspects of the attention mechanism." |
| **正例**（首句） | "The attention mechanism contributes 23% of our model's performance gain." |

**规则**：每段首句 = 该段论点的浓缩。后续句子是支撑。

**检查项**：每段首句是否能在去掉该段其他内容后独立传达一个完整主张？不能 → 重写。

---

### 段落与章节（4条）

---

#### 5.1 段落 = 主张 + 理由 + 证据

一段不是一堆句子的集合——是一个论证。缺少任何一个要素，就不是完整的论证。

| | 英文 |
|--|------|
| **反例** | "Attention mechanisms have been widely used in NLP. They allow models to focus on relevant parts of the input. In this paper, we also use attention." |
| **正例** | "Attention mechanisms improve NLP performance [主张]. Bahdanau et al. (2015) showed that attention captures alignment patterns [证据1]. Vaswani et al. (2017) further demonstrated that self-attention alone suffices for sequence transduction [证据2]. Therefore, we adopt a transformer-based architecture [理由→主张推进]." |

**检查项**：每段是否有明确的主张句？主张句后是否跟了理由或证据？——缺 → 标注结构不完整。

> **概念引入顺序检查**：段落中如果使用了尚未定义的概念（例如在第 2 段提到 "L2 loss" 但到方法章才解释），标注为悬空引用。后文才出现的概念在前文中使用时，必须至少给出一句示意性解释。

> **自创术语时效检查**（新增于 v1.5）：论文首次提出的术语（如 "Inverse ICL"、"demonstration interference"）首次出现后 3 段内，必须给出定义句或至少一句示意性解释——让读者不必跨节才能理解。超过 3 段仍未定义 → 标注为 ⚠️ 悬空术语。注意：标题和摘要中出现不算首次触发（读者预期后续解释），从正文首次出现段开始计数。

---

#### 5.2 IMRaD 逻辑顺序

论文不是按实验时间写的——是按论证逻辑写的。

| 章节 | 回答什么问题 | 不写什么 |
|------|-------------|---------|
| **引言** (I) | 为什么这个问题重要？前人做了什么？gap 在哪？ | 不写实验结果 |
| **方法** (M) | 你怎么做的？别人怎么复现？ | 不写"为什么"选这个方向（那是引言的事） |
| **结果** (R) | 你发现了什么？ | 不写"这意味着什么"（那是讨论的事） |
| **讨论** (D) | 你的发现意味着什么？局限在哪？ | 不重复结果部分的数字 |

**检查项**：相邻章节是否有内容重叠？引言是否偷跑了结果？讨论是否只重复了结果？→ 标注越界。

---

#### 5.3 CARS 引言三段式（Swales, 1990）

引言的第一段是整个论文最重要的 200 字——审稿人决定继续读还是毙掉的瞬间。

| 段 | 做什么 | 例子 |
|----|--------|------|
| **Move 1: 建立领域** | 说明这个领域重要/活跃/有共识基础 | "Machine translation is a core task in NLP with wide industrial application." |
| **Move 2: 建立空白** | 指出前人工作的 gap / 问题 / 不足 | "However, existing models rely on recurrence, which limits parallelization and scalability." |
| **Move 3: 填补空白** | 宣布本文做什么来填这个 gap | "We propose a transformer architecture that dispenses with recurrence entirely." |

**检查项**：引言第一段是否能识别出清晰的 Move 1 → Move 2 → Move 3 结构？少一段 → 标注。

> **宽松说明**：CARS 是高度结构化的模型，短论文/workshop 论文可接受压缩版（如 Move 1+2 合并为一句话）。Move 3 不可省略。

---

### 表达精度（13条）

---

#### 4.1 不确定性分级

科学写作中软弱的表达不是软弱——是精确。用对词。

| 级别 | 英文表达 | 中文表达 | 使用条件 |
|:---:|---------|---------|---------|
| 强断言 | "demonstrates" / "proves" | "证明" / "证实" | 核心实验直接验证 + 排除了所有替代解释 |
| 中置信 | "shows" / "indicates" | "表明" / "显示" | 证据充分但不能完全排除替代解释 |
| 弱暗示 | "suggests" / "is consistent with" | "提示" / "与……一致" | 证据指向此方向但存在多种可能解释 |
| 推测 | "may" / "is likely to" | "可能" / "倾向于" | 基于类推或间接证据 |

禁止表达："without doubt" / "undoubtedly" / "it is obvious that" —— 无论你多确定。

**检查项**：全文强断言使用的条件是否满足？每处强断言回溯到证据。

---

#### 4.2 具体数字优于模糊描述

| | 英文 | 中文 |
|--|------|------|
| **反例** | "The model significantly outperformed the baseline." | "模型显著优于基线。" |
| **正例** | "Our model achieved 87.3% accuracy, a 23% relative improvement over the baseline (p < 0.01, n=100)." | "我们的模型达到 87.3% 准确率，比基线提升 23%（p < 0.01, n=100）。" |

**禁止副词**："significantly" / "dramatically" / "substantially" 后必须跟具体数字。没有数字 → 删除副词。

**检查项**：全文"significantly"出现次数 = 数字支撑次数。不相等 → 删除或补数字。

> **反向约束**：4.2 要求的"具体数字"必须来自可溯源的数据。论文中自己报告的实验结果自然有数字——为它们增加精度是有意义的。但引用他人工作时，如果原文只给了"approximately 90%"，不应改写为"90.3%"。无来源的精确定量比有来源的模糊表述更危险。无法验证的数字 → 改为定性描述。

> **方法贡献型论文说明**：如果论文的核心贡献是提出新方法/新算法/新工具（而非报告新实证发现），可以接受摘要中不含数字——但建议至少用一个核心实验的数字锚定。如果方法本身没有附带任何实验验证，标注为"理论贡献型"。

---

#### 4.3 术语一致

同一个概念全文用同一个术语。一个概念换三个说法 = 读者以为你在讲三个不同的东西。

**反例**：同一篇论文中"信息瓶颈" 和 "信息压缩" 和 "representational bottleneck" 混用——读者不知道它们是同一个概念还是三个概念。

**检查项**：全文核心术语一致性。同一概念有无 2+ 种表述 → 统一。

---

#### 4.4 禁词清单

以下词在 ANR 学术产出中无权出现：

| 禁词（EN） | 禁词（ZH） | 理由 |
|-----------|----------|------|
| revolutionary | 革命性的 | inflated claim |
| first-ever / the first time ever | 史无前例 | 无限定条件，不可验证。论文中永远不说 |
| to the best of our knowledge, the first | 据我们所知，是首个 | 等于没查全文献——同下一条 |
| fundamentally new | 根本性创新 | inflated claim |
| it is obvious that | 显然/不言而喻 | 如果真的显然，不需要说；如果不说服不了自己，说"显然"没用 |
| to the best of our knowledge | 据我们所知 | 这条免责声明等价于"我没查全文献"。要么查全，要么说真话——"我们在 XYZ 范围内未发现相关工作" |
| simple / simply / elegant（自我评价型） | 简单的 / 优雅的（自评） | 自称自己的方法简单 → 必须在该句附近解释"为什么简单是贡献"。每次出现都必须有解释。中性技术描述（"a simple baseline"）不限制 |
| powerful / strong(ly) / effective | 强大的 / 有效的 | 自我评价。除非后跟具体数字，否则是空转修辞 |

> **细化规则**：允许 "the first to [具体场景] on [具体基准]"（限定条件清晰、可被挑战）——如"the first DRL model to play Atari games from raw pixels"。禁止 "first-ever"（无限制条件）。禁止 "to the best of our knowledge, the first..."（等于没查全文献）。

**检查项**：全文扫描上述禁词 → 全部删除或替换为可测量的表述。

> **AI 生成高频警示词**（新增于 v1.6 · 整合自 humanizer skill · v1.7 双语化）：
> 
> 以下词不是绝对禁词，但在 AI 生成文本中出现频率远超人类写作。每篇出现次数超过阈值时标注 ⚠️（非违规，供作者裁决）。
> 
> | 警示词（EN） | ZH 对等 | 阈值 | 说明 |
> |-------------|--------|:--:|------|
> | pivotal | 至关重要 / 关键性的 | 0 | 自称关键——让读者判断 |
> | showcase (v.) | 展示 / 彰显 | 0 | 学术论文用 "demonstrates" / "证明" |
> | underscore (v.) | 强调 / 凸显 | 0 | 用 "shows" / "表明" |
> | delve into | 深入探讨 / 深入剖析 | 0 | 删。说具体做了什么，不说"深入" |
> | tapestry | 画卷 / 编织 | 0 | 文学比喻，学术论文不该出现 |
> | testament (n.) | 见证 / 体现 | 0 | 用 "demonstrates" / "说明" |
> | vibrant | 蓬勃 / 生机勃勃 | 0 | 文学修饰，学术论文不该出现 |
> | interplay | 相互作用 / 交织 | 0 | 用具体的机制名称替代比喻 |
> | fostering | 培养 / 促进 | 0 | 空泛。说具体做了什么 |
> | invaluable | 无价的 / 宝贵的 | 0 | 自我评价。让读者判断价值 |
> | it is worth noting | 值得注意的是 / 值得一提的是 | 0 | 删。如果真值得注意不需要说 |
> | in this regard | 在这方面 | 0 | filler。删后不影响语义 |
> | a key role | 发挥关键作用 / 扮演重要角色 | 0 | 自我评价。或具体说作用是什么 |
> | crucial | 至关重要 | ≤1 | 全文最多1次。多则空洞 |
> | landscape (abstract) | 格局 / 版图 / 图景 | ≤1 | 具体说趋势，不用"格局"概括 |
> | furthermore / moreover | 此外 / 而且 | ≤2 | 各≤2。英文论文这两个词密度高是AI典型痕迹 |
> | notably | 值得注意的是 | ≤2 | ≤2。高密度出现是AI痕迹 |
> 
> **中文特有 AI 腔**（无英文直接对等，独立扫描）：
> 
> | 警示表达（ZH） | 阈值 | 操作 |
> |-------------|:--:|------|
> | 毋庸置疑 / 不言而喻 / 显而易见 / 众所周知 | 0 | 删。真的显然不需要说 |
> | 不仅……而且…… | ≤1 | 同段出现 ≥2 次 → ⚠️。AI最爱用这对关联词凑论证层次 |
> | 从而……进而……最终…… | 0 | 因果链堆叠——AI在假装递进。拆成平实陈述 |
> | 具有重要的理论意义和现实意义 | 0 | 万能空话。说具体意义 |
> | 为……做出了重要贡献 | ≤1 | 要么说具体贡献，要么删 |
> | 在……方面 / 从……角度 / 通过……的方式 | ≤2 | 三词合计 ≤2。AI用这些来绕弯——"在模型性能方面"→"模型的性能" |
> | 不可否认的是 / 必须承认的是 | 0 | 删。不否认就直接说 |
> | 极大程度上 / 在很大程度上 / 一定程度上（非数值语境） | ≤1 | 模糊修饰。有数字给数字，没数字删 |
> 
> **阈值说明**：0 = 建议完全不出现。≤1 / ≤2 = 可用但频繁出现是 AI 痕迹。
> 
> **容易误触的 AI 句式**（非禁词，但在同一段中出现 ≥2 个 → ⚠️）：
> - [EN] "serves as" / "stands as" / "boasts" 替代简单 "is" / "has"
> - [EN] "marking a / shaping the / setting the stage for" 句尾修饰
> - [EN] "highlighting its importance" / "underscoring its significance" 语义空转的 -ing 从句
> - [EN+ZH] "The future looks bright" / "未来可期" / "This represents a major step forward" 类万能结尾
> - [ZH] "综上所述" + 段尾无实质总结 → 删。要么写有内容的总结，要么直接结束

---

#### 4.5 引用即对话

引用不是"前人说了什么"——是"前人说了什么，你和他们什么关系"。

| | 英文 |
|--|------|
| **反例（报菜名）** | "Smith (2020) found X. Jones (2021) reported Y. Chen (2022) showed Z." |
| **正例（对话）** | "Smith (2020) demonstrated X in single-domain settings. Jones (2021) extended this to multi-domain, yet both methods assume known label distributions—an assumption that fails in our setting. We address this by..." |

**规则**：每段引用必须阐明：(a) 前人做了什么 (b) 有什么不适用于你的场景 (c) 你做了什么来推进。

**检查项**：纯罗列引用（连续 3+ 个 "Author (Year) found/verb..." 句，无连接词）→ 改写为对话。

---

#### 4.6 时态统一

| 内容 | 英文时态 | 中文时态 |
|------|:--:|------|
| 前人已发表的结论 | 现在时 | "Smith (2020) 证明 X 导致 Y" |
| 本研究的实验操作 | 过去时 | "我们在 100 个样本上运行了实验" |
| 本研究的发现/贡献 | 现在时 | "我们的结果表明 X 优于 Y" |
| 未来方向 | 将来时或现在时 | "未来的工作将探索……" |

**同一段落内不跳时态。** 如果一段同时引用前人结论和报告本实验，用过渡句标明切换："Building on Smith (2020), we designed an experiment to test..."
"在 Smith (2020) 的基础上，我们设计了一个实验来检验……"

**检查项**：每段时态一致性。同一段内过去时→现在时→过去时 → 标注为时态跳跃。

---

#### 4.7 标题传达发现

标题的理想形态 = 方法 + 发现 + 效果量。如果做不到——至少让读者读完标题就知道你发现了什么，而不是你"研究了"什么。

| | 英文 | 中文 |
|--|------|------|
| **反例（描述主题）** | "A Study of Machine Learning Methods for Stock Prediction" | "机器学习方法在股票预测中的应用研究" |
| **正例（传达发现）** | "Transformer-Based Models Improve Stock Return Prediction by 23% Over LSTM Baselines" | "Transformer 模型在股票收益预测中超越 LSTM 基线 23%：基于注意力机制的多市场验证" |

**规则**：标题不应以"A Study of..." / "Research on..." / "An Investigation of..." 开头——每一个研究都是 study，标题没有传达任何额外信息。

**例外**：如果本论文是某个方法/概念/领域命名的首创（如"Generative Adversarial Networks"），以方法名称作为标题是可接受的——此时方法名本身就是核心贡献。

**检查项**：标题去掉"研究""分析""探索"等空转词后是否有实质性名词/动词（方法名称算实质内容/首创命名）→ 合格。没有 → 重写。

---

#### 4.8 claim 可追溯（宽松规则）

> ⚠️ 本条为宽松检查。AI 可以识别"是否有引用标注"，但不能判断"证据是否充分"。

| | 英文 |
|--|------|
| **反例** | "Deep networks outperform shallow networks in all tested scenarios." — 无引用，无数字。纯断言 |
| **正例** | "Deep networks outperform shallow networks by 8-15% on ImageNet (He et al., 2016) and by 3-5 BLEU on translation tasks (Vaswani et al., 2017)." |

**规则**：如果一段中出现显式主张（非 hedging——"may" "suggest" 不算），检查该主张后是否至少跟了一个证据来源（引用或数据）。如果没有 → 标注为"⚠️ 无证据支撑"，不标违规。

**检查项**：每段中显式主张后是否跟了证据来源。无 → ⚠️（不标❌）。

---

#### 4.9 缩写管理

缩写是学术写作的默认设置——但大多数缩写对读者不是便利而是负担。

**首次出现必须给全称**：产品代号（GPT/BERT）、项目名称（ImageNet）、通用常识（LLM/GPU）不在此列。**关键判据：如果缩写指代的概念脱离上下文无法被目标读者理解，必须补充。**

**三问检判**：定义每个缩写的，问自己：① 后文会用到它 2 次以上吗？（用不到 → 不定义，直接用全称）② 这个缩写在摘要里出现过吗？（出现 → 摘要里也必须定义一次）③ 全文缩写总数超过 5 个？（超过 → 严重警告——考虑删掉不常用的）

**反例**："We propose MPC-based RL for VLA in POMDP settings." — 一句五个缩写，无一全称。

**正例**："We combine model predictive control (MPC) with reinforcement learning (RL) for vision-language-action (VLA) models in partially observable Markov decision process (POMDP) settings."

**检查项**：全文缩写总数 + 每个缩写是否在首次出现时定义了全称 → 标注违规位置和缺全称的缩写。

---

#### 4.10 因果语言审计

> 新增于 v1.3。基于真实论文审计实战经验。

自然科学和 ML 论文中，声称因果必须满足因果推断标准。大多数实验论文只建立相关性——用相关性词语。

**分级表：**

| 级别 | 词 | 需要满足的条件 |
|:---:|------|-------------|
| ❌ 禁止 | "causes" "explains" "is responsible for" "proves" | 需要 RCT 或因果推断方法——观察性实验不够 |
| ⚠️ 慎用 | "reveals" "confirms" "demonstrates" | 至少需要排除主要替代解释。用来描述"前人工作已被证明的事"可接受；描述本工作的发现应降级 |
| ✅ 安全 | "is associated with" "suggests" "is consistent with" "indicates" | 观察性实验的标准表达 |

**实战案例**（v1.3 审计中发现）：
- ❌ "a single prompt format change causing 0.57 accuracy swing" → ✅ "a single prompt format change associated with 0.57 accuracy swing"
- ⚠️ "This reveals fundamental divergence" → ✅ "This suggests fundamental divergence"
- ⚠️ "Phi's stability confirms format robustness through training data diversity" → ✅ "Phi's stability demonstrates that format robustness is achievable"

**检查项**：全文扫描 "causes" "explains" "reveals" "confirms" "proves" → 逐个对照上表确认级别是否匹配证据强度。

---

#### 4.11 数字对源验证

> 新增于 v1.3。论文中出现的每一个数字都必须有可追溯的来源。

**三层验证**：
1. 表格/正文中的数字是否直接等于实验数据（或经允许的汇总）？
2. 摘要中的数字是否与正文一致？
3. 正文不同节之间引用的同一数字是否一致？

**第四层：统计报告一致性**（新增于 v1.4）
4. 全文表格中，同类统计量（如 Δ 值、95% CI、p 值）的标注风格是否统一？一张表标了 CI、另一张没标 → 不一致。全文 ≥ 2 张表含差值/增益时检查

**实战案例**（v1.3 审计中发现）：51 个数字对源 JSON 逐一验证，查出正文 Table 4 中 llama3.1 noise50% 0.78 → 实际为 0.76。

**检查项**：提交前至少执行一次脚本化的"每个数字对源文件跑一遍校验"。

---

#### 4.12 摘要与正文一致性

> 新增于 v1.3。摘要是读者第一（也可能是唯一）阅读的内容——摘要中的每一项声称必须在正文中找到完全相同精度的支撑。

**检查项**：
- 摘要中每一条发现 → 在 Results 中找到对应数字和证据强度标记
- 摘要中的分组/归类（如 "Qwen/Llama peak at 2-shot"） → 正文中的对应分组是否同样成立？摘要可适度简化，但不得形成正文不支持的归类
- **摘要中的效果描述不得弱化正文中的统计显著性差异**（新增于 v1.4）：若正文显示非重叠 CI 确认了显著差异，摘要中说 "three models perform worse" 而未区分统计显著性 → 标注为精度降级，建议补充显著性标记
- **聚合值精度不得降低**（新增于 v1.5）：摘要中出现的聚合数字（如 "Llama gains +0.10"）必须与正文中每个对应值逐字比对。若正文实际存在多个值（如两个 Llama 模型分别为 +0.10 和 +0.11）而摘要只用了一个近似值 → 标注为 ⚠️ 精度降级，建议改为 "no more than +0.11" 或列出具体值。不可用整体判断替代逐数字比对
- 若正文结论比摘要更弱 → 修改摘要

**实战案例**：摘要写 "Qwen/Llama peak at 2-shot"，但正文中 Llama-3.1 从 2-shot 到 8-shot 几乎持平（0.78→0.76→0.76），不存在真正的峰值。修正为 "Qwen peaks at 2-shot"。

---

#### 4.13 引用完整性

> 新增于 v1.4。参考文献列表中的每一条都必须在正文中被引用，正文中引用的每条都必须出现在参考文献列表中。

**检查项**：
- 逐条比对：参考文献列表的条目 ↔ 正文中的引用标记，双向互查
- 未被引用的 bib 条目 → 标注（可能是废弃引用或正文漏标）
- 正文中出现但不在列表中的引用 → 标注（幽灵引用）
- 禁止凭印象判断——必须逐条对照源文件确认

---

#### 5.4 表格规范（条件触发）

> 新增于 v1.4。仅在用户已指定目标期刊/会议、且已加载该刊定位卡时触发。无定位卡 → 跳过本条。

不同期刊/会议对表格的要求不同——表头样式、CI 标注规范、数字精度、表格标题位置。当定位卡已加载时，skill 自动联网搜索该刊的表格规范（从投稿指南或近期发表论文中提取），并据此检查当前论文的表格。

**检查项**（定位卡加载后）：
- 表格标题位置：above（大多数 CS 会议如 NeurIPS/ICML）vs below（部分期刊）
- 数字精度一致性：同一列内小数位数是否统一
- CI/显著性标注方式：是否与该刊惯例一致（如 NeurIPS 偏好 ±std，ACL 偏好 95% CI）
- 表头层级：是否遵循该刊惯例（多层表头 vs 扁平表头）

**扫描范围**：至少扫该刊近 3 篇已发表论文的表格确认惯例，不凭记忆。

---

### 去AI化（1条 · 写后检查）

---

#### 6.1 去 AI 化自检清单

> ⚠️ 本条不参与生成阶段约束。写完初稿后逐条自检。

写好文章后，用以下清单再过一遍。AI 即使遵守了前面 27 条规则，训练数据的惯性仍可能产生"太顺滑"的文本。

**A. 结构层（原 6 条）**

| # | 检查项 | 操作 |
|:--:|--------|------|
| 1 | 是否有连续 3 句以上长度几乎完全相同的句子？ | 拆一句，或变一句长度 |
| 2 | 是否有"A、B、C"三点并列，每句字数恰好高度均匀？ | 打破对称——让其中一句明显更长或更短 |
| 3 | 是否有"值得注意的是"、"从某种意义上说"、"不言而喻"、"换言之"等空转短语？ | 删除。如果删了之后前后句接不上——说明前后句本来就不该接在一起 |
| 4 | 是否有段落结尾是"未来研究可以进一步探索……"式万能句？ | 要么给出 ≥1 个具体方向和具体为什么，要么删 |
| 5 | 读出声——有没有哪里特别顺？ | 顺滑段落 = 可能隐含逻辑跳跃。标注，让审阅者验证 |
| 6 | 每段的首句和末句——有没有形成"教科书式"的完美闭环？ | 科学论文不是教科书。允许开放结尾。 |

**B. 措辞层（新增于 v1.6 · 整合自 humanizer · v1.7 双语化）**

每条标注适用语言：`[EN]` `[ZH]` `[EN+ZH]`。扫描时根据文本语言跳过不适用的条目。

| # | 语言 | 检查项 | 操作 |
|:--:|:--:|--------|------|
| 7 | [EN] | 是否有 "serves as" "stands as" "boasts" 替代简单的 "is" "has"？ | 换回简单动词。"X serves as the primary method" → "X is the primary method" |
| 8 | [EN] | 是否有句尾 "-ing" 从句做语义空转补充？如 "highlighting its significance" "underscoring its importance"。 | 删。技术类 -ing 保留（如 "performing gradient descent"）。模糊修饰类 -ing — 删后不影响语义 → 删 |
| 9 | [EN+ZH] | 是否有 "marks a pivotal moment" / "标志着关键的转折" "represents a significant shift" / "代表了重大转变" "setting the stage for" / "为……奠定了基础" 等宣告式膨胀句？ | 降级为事实陈述。不说"标志着"，说具体发生了什么 |
| 10 | [EN+ZH] | 是否有 "Studies have shown" / "研究表明" "Experts believe" / "专家认为" "Industry reports suggest" / "行业报告显示" 等无来源归属？ | 要么加引用，要么删。可以泛引但句内必须见引用标记 |
| 11 | [EN] | 是否有英文 filler： "In order to" "Due to the fact that" "It is important to note that" "At this point in time"？ | "In order to"→"To"、"Due to the fact that"→"Because"、"It is important to note that"→删 |
| 12 | [EN+ZH] | 是否有 "The future looks bright" / "未来可期" "This represents a major step forward" / "这标志着迈出了重要一步" 等万能结尾？ | 删，或用具体计划替代 |
| 13 | [ZH] | 是否有 "毋庸置疑" "不言而喻" "众所周知" "不可否认的是" "必须承认的是"？ | 删。真的显然/不否认/众所周知——不需要说 |
| 14 | [ZH] | 是否有 "不仅……而且……" 同段出现 ≥2 次？是否有 "从而……进而……最终……" 因果链堆叠？ | 前者打散对称。"从而……进而……" 全删——拆成平实独立陈述 |
| 15 | [ZH] | 是否有 "具有重要的理论意义和现实意义" "为……做出了重要贡献" 等万能空话？ | 删。说具体意义、具体贡献 |
| 16 | [EN+ZH] | 是否有范畴词赘余？[EN] "in terms of" "in the field of" "with respect to" "regarding" / [ZH] "XX问题" "XX方面" "XX领域" "XX工作" | 删。"在模型性能方面"→"模型的性能"；"the field of NLP"→"NLP" |
| 17 | [EN+ZH] | 是否有 "XX性" / "-ity" 后缀堆砌？[EN] "criticality" "representativeness" "generalizability" — 学术论文不可避免但密集堆叠是 AI 痕迹 / [ZH] "重要性" "可行性" "必要性" "可能性" "鲁棒性" "有效性" "合理性" | 同段出现 ≥3 个 → ⚠️。替换策略：用动词替代名词化（"分析可行性"→"判断是否可行"） |
| 18 | [ZH] | 是否有虚词框架？"在……方面" "从……角度" "通过……的方式" "基于……的考虑" "在……过程中"（EN 等价已由 #11 覆盖） | 删框架，保留内容。"从提高效率的角度"→"为了提高效率"|

> ⚠️ 以下 humanizer 规则**不适用于学术写作**，切勿执行：
> - 消 hedging（"may" "suggest" "potentially"）——与 4.1 不确定性分级冲突。Hedging 是学术美德。
> - 术语换词避免重复（elegant variation）——与 4.3 术语一致冲突。学术写作要求同一概念固定用词。
> - 消被动语态——与 2.1 的主动优先不同。2.1 是"优先"不是"禁止"，被动语态在方法论章节有合法使用场景。

**检查项**：A 层 6 条全扫。B 层按语言标签扫描适用条目（B 层共 12 条：EN 适用 8 条，ZH 适用 9 条）。A+B 合计：EN 14 条，ZH 15 条。标记风险点，不强制修正。

### 7.1 初始论证审计攻击面（写作助手手动触发「审这段」）

> 用户输入「审这段」→ 主会话内序贯执行论证审计 + 事实校验。轻量级逻辑脆性检查——不是模拟审稿的替代品，是写后的第一道防线。

**四条攻击面**：

| # | 攻击面 | 检查什么 | 自动修（P0） | 标注（P1） |
|:--:|:--:|----------|------------|--------|
| 1 | 论证弱点 | 前提能否被反例击穿？推理链 P1→P2→C 缺的步是什么？ | 声称 A→B→C 但 B 不成立 → 删或改表述 | 证据相关但说服力不足 → 供用户裁定 |
| 2 | 结构陷阱 | 怀疑读者视角，这段引发哪几个未答问题？顺序是否打断逻辑流？ | 句中做未被证明的作者假设 → 加前提 | 段尾缺过渡 → ⚠️ 标注 |
| 3 | 声称-证据对齐 | 强断言排除了替代解释？数字有源？ | 相关→因果 越界 → 降级为 correlation 表述 | 数字无引用 → ⚠️ |
| 4 | 引用即对话 | 引用是否阐明：(a)前人做了什么 (b)不适用你的场景 (c)你推进了什么 | 纯罗列引用 → 拆一句加过渡 | 引用相关但未阐明差异 → ⚠️ |

**升级路径**：初始审计发现 P0 重复 3 次 → 自动提示用户「检查中发现多处论证脆性问题，建议跑一次完整的规范检查或模拟审稿」。不强制，仅建议。

### 7.2 事实校验攻击面（写作助手手动触发「审这段」）

> 初始论证审计（7.1）后序贯执行。独立子 Agent（「事实稽核员」模式），只读数字、引用、技术声明，不读修辞和结构。不做实验设计验证。

**四条攻击面**：

| # | 攻击面 | 检查什么 | 自动修/标注（P0） | 标注（P1） |
|:--:|:--:|----------|-------------------|--------|
| 1 | 数字有源 | 每个数字（百分比/数值/统计量）是否有内联引用或数据来源？ | 无来源 → 标注 `[source?]` | 来源模糊（"据报道"）→ ⚠️ |
| 2 | 强断言可回溯 | "demonstrates/proves/confirms/reveals/证明/证实/揭示" 每个对应正文哪条数据？ | 无数据支撑 → 降为 hedging | 有数据但因果链不完整 → ⚠️ |
| 3 | 引用-声称对齐 | 引用是否支持它所附的声明？（表述层检查——不打开 PDF 验证） | 引用方向与声称相反 → 改措辞 | 引用相关但不直接支持 → ⚠️ |
| 4 | 实验声明支撑 | "outperforms/achieves SOTA/significant improvement/显著优于/达到最优" 后是否跟具体数字？ | 空跑声明 → 删或补 `[data?]` | 有数字但无比较基线 → ⚠️ |

**边界**：不验证引用是否真实存在（4.11 的 JSON 对源负责此事）。不验证实验设计的统计正确性。这四条只做写作层面的「每个数字都能在文中找到声称的来源」匹配。

**跳过条件**：同 7.1——单短句、纯过渡、公式密集段跳过。数字/引用/技术声明密度为零的纯文本段落跳过。

**升级路径**：P0 重复 3 次 → 提示「多处校验问题，建议跑一次完整的规范检查（重点：4.2/4.8/4.11/4.12）」。仅在初始审计已触发升级时不重复。

---

## L3 · 文档类型对照表

| 规则 | 技术报告 | 学术论文 | 开题报告 | 中期报告 |
|------|:--:|:--:|:--:|:--:|
| **2.1** 主动语态优先 | ✅ | ✅ | ✅ | ✅ |
| **2.2** 短句 | ✅ | ✅ | ✅ | ✅ |
| **2.3** 一句一主张 | ✅ | ✅ | ✅ | ✅ |
| **2.4** 动作用动词 | ✅ | ✅ | ✅ | ✅ |
| **2.5** 避免嵌套从句 | ✅ | ✅ | ✅ | ✅ |
| **2.6** 人称统一 | "我们" | "本文"/"we" | "本研究" | "本研究" |
| **3.1** 已知→新信息 | ✅ | ✅ | ✅ | ✅ |
| **3.2** 动词就近主语 | ✅ | ✅ | ✅ | ✅ |
| **3.3** 压力位置 | ✅ | ✅ | ✅ | ✅ |
| **3.4** 段落首句即论点 | ✅ | ✅ | ✅ | ✅ |
| **4.1** 不确定性分级 | ✅ | ✅ | ⚠️ 开题可偏积极 | ⚠️ 诚实但不消极 |
| **4.2** 具体数字>模糊 | ✅ | ✅ | ⚠️ 无数据时允许 | ⚠️ |
| **4.3** 术语一致 | ✅ | ✅ | ✅ | ✅ |
| **4.4** 禁词清单 | ✅ | ✅ | ✅ | ✅ |
| **4.5** 引用即对话 | ✅ | ✅ | ✅ | ✅ |
| **4.6** 时态统一 | ✅ | ✅ | ✅ | ✅ |
| **4.7** 标题传达发现 | ✅ | ✅ | ✅ | — |
| **4.8** claim 可追溯 | ⚠️ 宽松 | ⚠️ 宽松 | ⚠️ 宽松 | ⚠️ 宽松 |
| **4.9** 缩写管理 🆕 | ✅ | ✅ | ✅ | ✅ |
| **4.10** 因果语言审计 🆕 | ✅ | ✅ | ⚠️ | ⚠️ |
| **4.11** 数字对源验证 🆕 | ✅ | ✅ | ✅ | ✅ |
| **4.12** 摘要一致性 🆕 | ✅ | ✅ | ⚠️ | ⚠️ |
| **4.13** 引用完整性 🆕 | ✅ | ✅ | ✅ | ✅ |
| **5.1** 段落=主张+理由+证据 | ✅ | ✅ | ✅ | ✅ |
| **5.2** IMRaD 逻辑顺序 | ✅ | ✅ | ⚠️ 开题可用自身结构 | ⚠️ |
| **5.3** CARS 引言三段 | ✅ | ✅ | ✅ | — |
| **5.4** 表格规范 🆕 | ⚠️ 有定位卡时触发 | ⚠️ 有定位卡时触发 | — | — |
| **6.1** 去AI化自检 | ✅ | ✅ | ✅ | ✅ |

> ✅ = 完全适用。⚠️ = 适用但有权重调整（见标注）。— = 不适用。

**技术报告 vs 学术论文的唯一区别**：
- 技术报告用"我们"做主语，记录真实过程。可以包含失败和死胡同。
- 学术论文用"本文"/"we"做主语，呈现重构后的论证直线。不包含失败（除非作为 limitation）。
- 其余规则两种文档完全相同。

---

## 附录 · 常见反模式清单

| # | 反模式 | 违反的规则 | 表现 | 修复 |
|:--:|--------|----------|------|------|
| 1 | **inflated claims** | 4.1, 4.4 | "revolutionary" "first-ever" "fundamentally" | 用精确表达替代——你的工作的边际贡献 |
| 2 | **名词化堆砌** | 2.4, 2.2 | "The implementation of the optimization of the parameter selection was conducted." | 找动词——"We optimized parameter selection." |
| 3 | **阴影主语** | 2.1, 3.2 | "It is believed that..." "It has been shown that..." | 说出谁相信、谁展示的 |
| 4 | **完美排比** | 6.1 | 连续 3 段 "First,... Second,... Third,..." 每段字数高度均匀 | 打破一段的对称——让其中一段明显更长或更短 |
| 5 | **免责式 limitation** | 4.2, 原则 4 | "Future work may explore applying this to other domains." | 要么给 ≥1 个具体方向 + 为什么现在没做，要么删 |
| 6 | **缝合过渡** | 2.2, 6.1 | "值得注意的是""换言之""从这个角度看" 密度 > 每段 2 个 | 删除空转短语。如果删后接不上——说明前后本来就不该接 |
| 7 | **参考文献报菜名** | 4.5 | "Smith found X. Jones reported Y. Chen showed Z." 三连无关系 | 每一段引用阐明：(a)前人做了什么 (b)不适用你的地方 (c)你做了什么推进 |
| 8 | **SOTA 播报** | 4.2, 2.3 | 摘要中连续 3+ 个 "achieves state-of-the-art on dataset X, Y, Z"——读者无法判断哪个是核心贡献 | SOTA 是结果不是贡献。贡献是为什么 SOTA——用一个最关键的领域说明即可 |
| 9 | **因果越界** 🆕 | 4.10, 4.1 | "X causes Y" "X reveals Y" "X confirms Y through Z"——观察性实验被表述为因果发现 | 用相关性词语替换——"is associated with" "suggests"；只说观察到了什么，不推测原因 |

---

## 与 ANR 流程的整合

| 环节 | 加载/使用方式 |
|------|-------------|
| **阶段 3 文章构建** | AI 在生成初稿时自动对标本规范 |
| **三阶自修订 R3** | R3 措辞审查逐条检查 L2 的全部生成规则（不含 6.1） |
| **阶段 5 审阅迭代** | 审阅者可引用特定规则编号指出问题（如"规则 4.5 引用即对话——你这段在报菜名"） |
| **阶段 6 交付前** | 6.1 去AI化自检清单执行一次 |
| **评价框架 D5.1** | 每一条 L2 规则 = D5.1 评分的具体证据来源 |

---

## 变更日志

| 日期 | 说明 |
|------|------|
| 2026-06-12 | v2.5.0 精简：写作助手手动触发审计、模拟审稿并行→序贯、引用角色分类、对抗自检注入规范检查 |
| 2026-06-12 | 新增论文定位模式（Gap扫描→贡献坐标系→竞争度检查，强制联网 ≥2 轮） |
| 2026-06-12 | 新增事实校验攻击面（数字有源/强断言可回溯/引用-声称对齐/实验声明支撑） |
| 2026-06-12 | 6.1 B 层新增 #16-18：范畴词赘余 / X性通胀 / 虚词框架 |
| 2026-06-12 | 新增初始论证审计攻击面（4 条攻击面 + P0 自动修 / P1 标注） |
| 2026-06-12 | 双语化：4.4 高频警示词 EN/ZH 双列 + 中文特有 AI 腔 8 项；6.1 B 层语言标签 + 新增 #13-15 |
| 2026-06-12 | 整合 humanizer：4.4 新增 AI 生成高频警示词表（15 词 + 阈值）+ 易误触句式（4 类）；6.1 去AI化自检 6→12 条 |
| 2026-06-11 | ICL论文模拟审稿实战提炼：4.12 新增聚合值精度；5.1 新增自创术语时效检查 |
| 2026-06-11 | 移入四项编辑检查：4.11 第四层统计报告一致性、4.12 摘要显著性区分、4.13 引用完整性、5.4 表格规范。规则总数 25→28 |
| 2026-06-10 | 新增 4.10 因果语言审计（3级词表+实战案例）+ 4.11 数字对源验证（3层）+ 4.12 摘要一致性；反模式新增因果越界。规则总数 22→25 |
| 2026-06-03 | 独立 skill 场景适配：新增段落与章节 3 条（5.1-5.3）+ 4.8 claim 可追溯。规则总数 17→21 |
| 2026-06-03 | 初始版本。基于 Zinsser / Gopen & Swan / Booth / Medawar / Feynman / Hyland / Swales 六位来源。17条规则 + 7项反模式 + 4文档类型对照 |
