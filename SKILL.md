---
name: research-paper-suite
description: Research paper project assistant for academic writing, positioning, argument extraction, object-level issue targeting, style checking, venue fit, mock review, rebuttal planning, manuscript assembly, visualization, and stateful paper workflows. Use when Codex is working on a research paper project that needs structured state, artifacts, expert routing, proposal validation, event-log tracking, Claim/Evidence/ReasoningStep graphs, LaTeX/Markdown/PDF ingestion or export, review/rebuttal workflows, object graph visualization, or submission readiness checks. Do not use for ordinary lightweight sentence polishing, generic writing advice, or general Q&A that does not need paper project state.
---

# Research Paper Suite

Use this skill as a thin project workflow entrypoint. Do not load every expert brief up front. Route first, then read only the files required for the chosen workflow.

## Installing And Upgrading

Install from a package checkout with the manifest-driven installer. Never merge this package into an existing skill directory with `cp -r`, `Copy-Item`, or archive extraction:

```powershell
python scripts/install_skill.py <target_skill_dir>
```

If the target already exists, inspect it first and use an explicit replace. The installer creates a timestamped sibling backup and stages a complete manifest-validated copy before swapping it into place:

```powershell
python scripts/install_skill.py <target_skill_dir> --replace
```

## Core Rules

- Treat suite-triggered work as paper project work with state, artifacts, proposals, and event log.
- Do not use this suite for ordinary lightweight writing help or generic Q&A.
- Do not directly edit `state/paper.yml` except through projection scripts.
- Do not let expert workers append to `events/event_log.yml`.
- Do not put long manuscript text into event payloads; write long text as artifacts.
- Do not write API keys, provider tokens, passwords, or other secrets into event logs, state, proposals, artifacts, visualization JSON, handoff manifests, or committed files. Store only `secret_ref` / provider metadata; see `references/backend_secret_management.md`.
- Do not create ad hoc project-level HTML pages, dashboards, or "friendly overview" pages by default. The canonical inspectable page is `visualization/index.html`, exported by `scripts/export_project_visualization.py`.
- If the user explicitly asks for an additional HTML preview or presentation page, record it as an `Artifact` proposal with an appropriate artifact type and path. Do not leave untracked files such as `outputs/paper-overview.html` or `outputs/paper-draft.html`.
- Do not read all expert briefs in one turn. Use route decisions and invocation packets.
- Prefer object-level issue targets: `Issue.target_object_type` / `Issue.target_object_id` should point to the smallest relevant `Claim`, `Evidence`, `ReasoningStep`, `Result`, `Section`, `Artifact`, or other semantic object.
- Use explicit links for argument structure, such as `claim_supported_by_evidence`, `claim_supported_by_reasoning_step`, and `issue_targets_object`.
- Use `SourceSpan` anchors for extracted semantic objects when available. New `claim.created`, `evidence.created`, `result.created`, and `citation.created` proposals should cite `references.source_span_ids` or explain `rationale.unanchored_reason`.
- Treat search output as intake data, not as final citations. Import structured search results into `SearchRun`, `ExternalWork`, and `SearchResult`; only create a `Citation` after an expert or user decides that an `ExternalWork` is relevant, then link it with `citation_represents_external_work`.
- Treat title-only or ordinary bibliographic ExternalWork records as unverified leads. Their Citations must be `tentative` and cannot be linked to Claim/Evidence as support. A `verified` Citation requires auditable `abstract` or `full_text` metadata.
- Literature selection must cover verified predecessor, direct competitor, later extension, and limitation roles. A missing role is acceptable only when represented by an open, object-targeted `citation_gap` Issue with `missing_literature_role`.
- Treat an invocation packet's mode as requested intent, not proof of isolation. After execution, record the actual backend with `record_expert_execution.py`; current-agent fallback must remain explicitly unverified and include a reason.
- When a fix or repositioning changes an issue's current risk, propose `issue.severity_changed` with `previous_severity`, `severity`, and `reclassification_reason`; if the issue is solved, also propose `issue.status_changed` to `resolved`.
- High-impact proposals must include proposal-level `rationale` and `references` as required by `dynamic/action_policy.yml`; do not hide the reason inside `payload`.
- Human approval is required for claim changes, venue changes, issue resolution or severity reclassification, final submission, rejecting reviewer fixes, arguing against reviewers, and checkpoint compaction.
- Generated projects must pass project acceptance before being handed off for user testing: durable files are recorded as existing Artifact objects, sources are auditable through traceable Citation/Artifact/ExternalWork links, Evidence has no placeholders or dangling artifact/citation references, and long drafts live in artifacts rather than large `Section.content` fields.
- After applying changes, do not end with only an artifact card or terse status line. Give the user a short beginner-facing completion note: what changed, what it means for the paper, what is still open, and where to test or inspect it.

## First Step

If a user request clearly belongs to a research paper project, read:

- `dynamic/router.md`
- `dynamic/route_decision_contract.md`
- `dynamic/action_policy.yml`
- `dynamic/workflows.yml`
- `dynamic/experts.yml`
- `dynamic/invocation_policy.yml`

Then produce or request a `route_decision.yml` that follows `dynamic/route_decision_contract.md`.

Validate a route decision with:

```powershell
python scripts/validate_route_decision.py <route_decision.yml>
```

## Project Setup

For a new empty paper project:

```powershell
python scripts/create_empty_project.py <project_dir> --paper-id <paper_id> --title "<title>" --stage idea
```

For existing `.tex` or `.md` input:

```powershell
python scripts/ingest_paper_project.py <input.tex-or-md-or-dir> --out-dir <project_dir> --paper-id <paper_id>
```

For raw PDF input, route through controlled document intake before expert work. Experts should read normalized artifacts and extraction reports, not parse raw PDF freely:

```powershell
python scripts/ingest_pdf_project.py <input.pdf> --out-dir <project_dir> --paper-id <paper_id> --title "<title>"
```

For structured search output, route through literature intake before asking an expert to select references:

```powershell
python scripts/fetch_search_results.py semantic_scholar "<query>" --limit 20 --out <project_dir>/artifacts/search-results.yml
python scripts/import_search_results.py <project_dir> <search-results.yml-or-json-or-csv> --out <project_dir>/proposals/search-intake.yml
python scripts/apply_action_proposals.py <project_dir> <project_dir>/proposals/search-intake.yml --actor system --dry-run
```

If a promising ExternalWork lacks an abstract, retrieve metadata through an approved provider, save the provider response as YAML or JSON, and import it as an auditable Artifact plus ExternalWork update:

```powershell
python scripts/import_work_metadata.py <project_dir> <external_work_id> <metadata.yml-or-json> --metadata-source-uri <https-url> --out <project_dir>/proposals/work-metadata.yml
python scripts/apply_action_proposals.py <project_dir> <project_dir>/proposals/work-metadata.yml --actor system --dry-run
```

Provider API keys and polite-pool contact values are runtime configuration only. Do not write raw keys, tokens, or personal contact values into events, state, artifacts, proposals, visualization JSON, or handoff manifests.

## Literature Selection

After `literature_intake` has committed `ExternalWork` candidates, route citation selection to `literature_selection`.

Use `positioning_expert` with `dynamic/templates/literature_selection.md`. The expected proposals are `citation.created`, `link.created`, and optional object-targeted `issue.created`. Selected citations must cite `references.external_work_ids`, state `verification_status` and `positioning_role`, and then create `citation_represents_external_work`. Only verified citations backed by abstract/full-text metadata may use `claim_uses_citation` or `evidence_uses_citation`; otherwise create a targeted open issue instead of pretending the work supports the claim.

Validate route and proposals with:

```powershell
python scripts/validate_route_decision.py <literature-selection-route.yml>
python scripts/apply_action_proposals.py <project_dir> <proposals.yml> --actor positioning_expert --dry-run
python scripts/validate_literature_coverage.py <project_dir>
```

## Argument Extraction

When the user asks to split arguments, build an object graph, run claim-evidence audit, or prepare structured context before review/style/writing, route to `argument_extraction` before the downstream expert.

Use `positioning_expert` with `dynamic/templates/argument_extraction.md`. The expected proposals are `claim.created`, `evidence.created`, `reasoning_step.created`, optional `result.created` / `citation.created`, `link.created`, and object-targeted `issue.created`. When normalized source spans exist, extracted semantic objects should cite them through `references.source_span_ids`; citations selected from imported literature should cite `references.external_work_ids` and create a `citation_represents_external_work` link.

Validate a route fixture or proposal file with:

```powershell
python scripts/validate_route_decision.py <argument-extraction-route.yml>
python scripts/apply_action_proposals.py <project_dir> <proposals.yml> --actor positioning_expert --dry-run
```

Apply only after dry-run succeeds:

```powershell
python scripts/apply_action_proposals.py <project_dir> <proposals.yml> --actor positioning_expert
```

For a config sanity check:

```powershell
python scripts/validate_layers.py
```

## Single Expert Execution

For formal single-expert work, prepare an isolated expert invocation. Do not load the expert brief into the main agent unless only inspecting or editing the skill itself.

```powershell
python scripts/prepare_expert_invocation.py <project_dir> <expert_name> --task "<task>"
```

The worker should read only the generated invocation directory:

- `runner_manifest.yml`
- `worker_packet.md`
- `expert_brief.md`
- `expert_output_contract.md`
- `action_policy.yml`
- `task.md`
- `input_snapshot/paper.yml`

Expected worker outputs:

- `outputs/report.md`
- `outputs/proposals.yml`

Workers must not create project-level preview webpages or other side files unless the task explicitly requests them. Any file that should persist beyond the invocation report must be proposed as an `artifact.created` event.

Packet preparation does not prove that an isolated worker actually ran. Immediately after execution, record the real backend:

```powershell
python scripts/record_expert_execution.py <invocation_dir> --backend isolated_worker --recorded-by <runtime>
```

If the platform used the current agent as fallback, record that fact and why. Do not label the report as isolated:

```powershell
python scripts/record_expert_execution.py <invocation_dir> --backend current_agent_fallback --recorded-by <runtime> --reason "Platform worker isolation unavailable."
```

After the worker writes proposals, validate and apply them from the main agent:

```powershell
python scripts/apply_action_proposals.py <project_dir> <invocation_dir>/outputs/proposals.yml --actor <expert_name> --dry-run
python scripts/apply_action_proposals.py <project_dir> <invocation_dir>/outputs/proposals.yml --actor <expert_name>
```

If a proposal contains approval-required actions, formal apply must stop unless the user has explicitly approved it. After approval, record that decision in the event log:

```powershell
python scripts/apply_action_proposals.py <project_dir> <proposals.yml> --actor <expert_name> --approved-by <user_name> --approval-summary "<what the user approved>"
```

For reusable demo proposals whose `paper_id` may not match the current project, add `--use-project-paper-id`.

High-impact proposals such as `claim.updated`, `paper.target_venue_set`, `issue.status_changed`, `issue.severity_changed`, `decision.recorded`, `checkpoint.created`, and `submission.finalized` must also pass the action policy: include `rationale`, cite existing objects/events through `references`, and keep approval pending until the user explicitly approves.

## Review Execution

For mock review, cold-read, or independent critique, use the review workflow instead of a single inline expert.

```powershell
python scripts/prepare_review_run.py <project_dir> --review-id <review_id> --runner-backend manual_packets
```

Reviewer workers must read only their role packet and frozen snapshot, then write role outputs. Aggregate after role outputs exist:

```powershell
python scripts/aggregate_review_reports.py <project_dir>/reviews/<review_id>
```

Then dry-run and apply the aggregate proposals:

```powershell
python scripts/apply_action_proposals.py <project_dir> <project_dir>/reviews/<review_id>/ac_proposals.yml --actor review_expert --dry-run
```

## Expert Briefs

Read one expert brief only after route decision or invocation preparation indicates it is needed:

- `dynamic/experts/positioning.md`: gap, contribution, competition, claim strength.
- `dynamic/experts/writing.md`: section drafting, rewriting, issue-driven revision.
- `dynamic/experts/style.md`: writing diagnostics, style and structure risks.
- `dynamic/experts/venue.md`: venue profile, submission constraints, audience fit.
- `dynamic/experts/review.md`: cold-read review and claim-evidence audit.
- `dynamic/experts/rebuttal.md`: reviewer comments, response strategy, rebuttal plan.
- `dynamic/experts/assembly.md`: manuscript artifacts, LaTeX/PDF, readiness gates.
- `dynamic/templates/argument_extraction.md`: Claim / Evidence / ReasoningStep extraction and support-link proposal template.
- `dynamic/templates/literature_selection.md`: ExternalWork-to-Citation selection and citation-link proposal template.
- `references/backend_secret_management.md` if the request touches API keys, provider configuration, backend AI runtime, or secret storage.

## Common Scripts

- `scripts/install_skill.py`: validate `skill_manifest.yml` and perform a clean install or explicit backup-and-replace; never merges into a stale skill directory.
- `scripts/validate_layers.py`: validate ontology / kinetic / dynamic references.
- `scripts/event_log.py`: demo, validate-log, and project event logs.
- `scripts/apply_action_proposals.py`: validate proposals, enforce action policy / approval gates, reject links whose endpoints do not exist in state or earlier proposals, and append events.
- `scripts/propose_event_revert.py`: generate an append-only compensating proposal for a committed update/upsert event.
- `scripts/checkpoint_event_log.py`: create/list/restore checkpoints.
- `scripts/export_tex_from_state.py`: export state projection to editable LaTeX.
- `scripts/export_bib_from_state.py`: export `Citation` objects to a `bibliography_bib` BibTeX Artifact; use before manuscript assembly when citations exist but no `.bib` artifact exists.
- `scripts/ingest_pdf_project.py`: controlled PDF intake; records source PDF, extracted text if available, extraction report, and extraction risk issues.
- `scripts/extract_source_spans.py`: split a recorded text artifact into `source_span.created` proposals with stable locators and text hashes.
- `scripts/fetch_search_results.py`: fetch Semantic Scholar / Crossref / OpenAlex / arXiv search results into an importable search-results YAML file.
- `scripts/import_search_results.py`: normalize YAML / JSON / CSV search results into SearchRun, ExternalWork, SearchResult, and search-link proposals.
- `scripts/import_work_metadata.py`: copy auditable provider metadata into an Artifact and propose an ExternalWork enrichment to `metadata_quality: abstract`.
- `scripts/validate_literature_coverage.py`: require verified predecessor, direct competitor, later extension, and limitation coverage, or targeted open citation-gap issues.
- `scripts/record_expert_execution.py`: record the actual invocation backend and whether worker isolation was verified.
- `scripts/run_style_check.py`: run the reused quick scan and emit review/issues.
- `scripts/lookup_venue_profile.py`: list or match cached venue profiles.
- `scripts/export_project_visualization.py`: export static `visualization/index.html` plus the full bundle, including literature verification/positioning coverage, Evidence -> SourceSpan -> Artifact provenance chains, and requested-versus-actual expert execution records.
- `scripts/validate_project_acceptance.py`: validate a generated project before handoff; catches untracked durable files, missing Artifact files, dangling Evidence source references, untraceable Citation objects or broken Citation-to-ExternalWork links, placeholder Evidence, missing SourceSpan anchors for submission-stage strong claims, and long section text stored in state/events. Evidence may be sourced directly by Artifact/Citation or indirectly through a valid `evidence_anchored_to_source_span` -> SourceSpan -> Artifact chain.
- `scripts/handoff_project.py`: run project acceptance, write `handoff_manifest.yml`, export the canonical visualization, and record formal output hashes.

## Backend Secrets

Secrets are runtime configuration, not project state. A future backend may provide a settings page where users submit API keys, but committed project records must contain only references:

```yaml
ai_provider:
  provider: openai
  model: gpt-5
  secret_ref: local:user-default-openai
```

Never include raw keys in prompts, event payloads, artifacts, handoff manifests, visualization JSON, or release packages. If a key is accidentally committed or shared, tell the user it must be rotated.

Before handing a generated project to the user for real testing, run:

```powershell
python scripts/handoff_project.py <project_dir>
```

If the manifest status is `failed`, return the problem list instead of presenting generated pages or artifacts as final outputs. `accepted_with_warnings` may be handed off only with the warnings stated plainly.

## Semantic Revert

Committed events are never deleted or edited. To undo an already committed update, generate a compensating proposal and apply it through the normal proposal validator:

```powershell
python scripts/propose_event_revert.py <project_dir> <event_id_or_offset>
python scripts/apply_action_proposals.py <project_dir> <generated_proposal.yml> --dry-run
python scripts/apply_action_proposals.py <project_dir> <generated_proposal.yml> --approved-by <name>
```

The first revert slice supports update/upsert object events whose changed fields existed before the target event. `issue.severity_changed` is handled as a special reclassification revert: the compensating event restores current `severity` while recording the pre-revert severity in `previous_severity`. The script refuses to generate a proposal when later events changed the same object fields, unless explicitly run with `--allow-conflicts`. Approval-required actions remain approval-required after revert proposal generation.

## Visualization

To inspect an auditable project state, export a local static page:

```powershell
python scripts/export_project_visualization.py <project_dir>
```

The page is split into hash-routed static pages: Overview, Graph, Timeline, Issues, Evidence & Files, and Audit. It includes Project Tracking Model, expandable Object Link Graph with per-object event history, Change Timeline, Open Review Issues, Evidence Trail, Project Files & Artifacts, and a collapsed Audit / Debug Details section. The normal user view should show paper-state concepts; action/function inventory belongs in the audit/debug section and is derived from `event_log.yml`, kinetic action definitions, projected objects, explicit links, and schema references. Export does not call an LLM.

For formal handoff, prefer `handoff_project.py`; it exports the canonical visualization and records the generated files in `handoff_manifest.yml`. If you manually re-export a formal visualization, require an accepted manifest:

```powershell
python scripts/export_project_visualization.py <project_dir> --require-accepted
```

Resolved, rejected, and wont-fix issues are shown as project history rather than active blockers. A former P0/P1 remains auditable through `previous_severity` and the event log, while the visible open-issue count only tracks unresolved issues.

Do not generate separate decorative overview pages as a substitute for this visualization. A user-facing explanation belongs in the chat completion note or `outputs/report.md`; durable files belong in artifact records.

## User-Facing Completion

When a workflow commits events, edits configuration, exports visualization, or creates artifacts, close the loop in plain language. Keep it short, but include:

- what changed;
- why the change matters to a non-expert paper author;
- what remains unresolved or needs user approval;
- the exact project path, artifact path, or visualization path when relevant.

Avoid cold handoffs such as "validated, modified actions.yml" followed only by a file card. The user should not have to open files just to learn whether the paper state improved.

## References

Load references only when the selected workflow needs them:

- `references/venue_profiles/`: cached venue profile library.
- `references/style_rules/rules.md`: staged writing rules.
- `references/output_templates/output_templates.md`: staged output templates.
- `references/review/reviewer_roles.md`: reviewer role guidance.
- `references/assembly/latex_pdf_rules.md`: assembly and compile guidance.
- `references/reuse_inventory.md`: reused assets inventory.

## Output Contract

Expert state changes must be expressed as proposals following `dynamic/expert_output_contract.md`.

Route decisions must follow `dynamic/route_decision_contract.md`.

If no state change is needed, output:

```yaml
proposals: []
```

## Running Scripts

Prefer running scripts from the skill root when using relative example paths. Absolute project paths are also acceptable.

On Windows, terminal encoding may garble Chinese display text; this does not affect YAML/JSON files written with UTF-8.
