# Manuscript Assembly Output

paper_id: <paper id>
target_venue_id: <venue id or none>
timestamp: <YYYYMMDD-HHMMSS>

## Artifacts

- manuscript_md: <artifact id/path>
- manuscript_tex: <artifact id/path>
- manuscript_pdf: <artifact id/path or not_generated>
- bibliography: <artifact id/path or none>

## Structure Check

- abstract: present | missing
- introduction: present | missing
- method: present | missing
- experiments/results: present | missing
- discussion/conclusion: present | missing
- limitations/ethics: present | missing | not_required

## Format Check

- page_or_word_limit: pass | warning | fail | unknown
- abstract_limit: pass | warning | fail | unknown
- heading_depth: pass | warning | fail
- figure_table_numbering: pass | warning | fail
- bibliography_ready: pass | warning | fail

## Compile Check

- latex_environment: present | missing | unknown
- pdf_compile: pass | fail | not_attempted
- log_artifact: <artifact id/path or none>

## Blocking Issues

- <issue id or none>
