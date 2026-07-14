# LaTeX / PDF Assembly Rules v0.1

用于后续 `assembly_expert` 和 manuscript assembly workflow。当前是 staging reference，不是最终实现。

## Boundaries

- 只组装已有章节，不生成新的研究内容。
- `.tex` 是交付物；生成后由用户自行管理。
- 每次组装生成新的 timestamped artifacts，不覆盖历史文件。
- 缺少目标 venue 时，降级为通用 `article` + IMRaD 骨架。

## Inputs

- `paper.yml` projection
- Section content / section artifacts
- Bibliography artifacts
- `venue_card` if available
- unresolved Issue list

## Assembly Checks

- 至少有摘要和两个正文章节。
- 对照 venue_card 检查章节顺序、摘要限制、页数/字数限制。
- 检查标题层级不超过约定深度。
- 检查图表编号连续，且正文有引用。
- unresolved P0 issue 应阻止 `submission.finalized`。

## Venue-Aware LaTeX

真实投稿前必须以官方 guideline / template 为准。

When target venue exists:

- 查找官方 LaTeX template / author guideline / submission format。
- 记录 template source、documentclass、required packages、bibliography style、anonymous mode、supplement rules。
- 找不到官方模板时，降级为通用 `article`，并创建 `format_risk` issue。

## PDF Compile

- 优先检测本地 `pdflatex`。
- 若存在：运行 LaTeX -> BibTeX if needed -> LaTeX x2。
- 若失败：保留 `.tex` and `.log`，创建 `format_risk` issue。
- 若不存在：只生成 `.tex`，创建或报告环境缺失 issue，不静默跳过。

## Outputs

- `manuscript_md`
- `manuscript_tex`
- `manuscript_pdf` if compiled
- `style_report` or assembly report artifact
- `issue.created` for missing sections / format risk
- `submission.finalized` only after human approval
