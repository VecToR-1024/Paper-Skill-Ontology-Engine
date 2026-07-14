# Research Paper Suite

[中文](README.md) | **English**

Research Paper Suite is an auditable workflow prototype for the full research-paper lifecycle. Instead of compressing research writing into one oversized prompt, it stores paper entities, sources, revisions, and approvals as structured state that can be validated and replayed.

- Current version: `0.2.2`

```text
LLM experts make semantic and writing judgments
        |
        v
proposals.yml describes suggested state changes
        |
        v
deterministic scripts validate references, policies, and approvals
        |
        v
event_log.yml appends accepted events
        |
        v
paper.yml projects the current state
        |
        v
acceptance, handoff, and visualization provide delivery checks
```

## Why This Project Exists

Many research-writing agents leave rules, context, and intermediate outputs inside chat history. They may produce useful prose, but they struggle to answer basic audit questions consistently:

- Where did this Claim come from?
- Is this Evidence anchored to an actual source passage?
- Is a paper merely a search candidate, or has it been verified and used in the argument?
- Which expert proposed a change, and who approved it?
- Can the current `paper.yml` be rebuilt from history?
- Can the work continue after switching agents or platforms?

Research Paper Suite turns those questions into explicit objects, links, events, and gates. The goal is not a longer prompt. The goal is a research workflow that is easier to audit, recover, and iterate.

## What It Is Not

- It is not a single giant prompt containing every research-writing rule.
- It is not a free-form editor where experts directly mutate `paper.yml`.
- It does not treat search results as evidence automatically.
- It is not yet a production backend with concurrent writers and remote worker orchestration.

## The Workflow in Five Minutes

A typical workflow for an existing paper looks like this:

```text
PDF / TeX / Markdown
  -> controlled intake
  -> Artifact + Extraction + SourceSpan
  -> expert invocation packet
  -> report.md + proposals.yml
  -> dry-run validation
  -> human approval when required
  -> append-only events
  -> projected paper state
  -> literature / provenance / issue checks
  -> handoff + static visualization
```

Three constraints define the system:

1. Experts submit proposals. They never edit committed state directly.
2. The event log is the source of truth. `paper.yml` is a rebuildable projection.
3. High-impact actions such as changing the main claim, selecting a venue, rejecting reviewer requests, or creating checkpoints require a human gate.

## Quick Start

In the commands below, `python` means the Python interpreter configured for this project.

### 1. Validate the suite

```powershell
python scripts/validate_layers.py
python scripts/check_repository_hygiene.py .
python -m pytest -q
```

### 2. Create a paper project

Start from an empty project:

```powershell
python scripts/create_empty_project.py work/my-paper `
  --paper-id P-my-paper `
  --title "My Paper" `
  --stage idea `
  --reset
```

Start from a PDF:

```powershell
python scripts/ingest_pdf_project.py paper.pdf `
  --out-dir work/my-paper `
  --paper-id P-my-paper `
  --title "My Paper"
```

Use `scripts/ingest_paper_project.py` to import TeX, Markdown, or an existing paper directory.

### 3. Validate and commit proposals

Always dry-run first:

```powershell
python scripts/apply_action_proposals.py work/my-paper proposals.yml --dry-run
```

Commit only after validation succeeds:

```powershell
python scripts/apply_action_proposals.py work/my-paper proposals.yml
```

Actions behind a human gate must record an approver explicitly:

```powershell
python scripts/apply_action_proposals.py work/my-paper proposals.yml `
  --approved-by user `
  --approval-summary "Approved after reviewing the proposed claim changes."
```

### 4. Open the static visualization

```powershell
python scripts/export_project_visualization.py work/my-paper
```

Open the generated file:

```text
work/my-paper/visualization/index.html
```

### 5. Prepare a formal handoff

```powershell
python scripts/handoff_project.py work/my-paper
```

This runs project acceptance, writes `handoff_manifest.yml`, exports the canonical visualization, and records hashes for key outputs.

## Static Visualization

`visualization/index.html` is the standard human-readable project view. It opens directly and does not require a web server.

| Page | What it shows |
|---|---|
| Overview | Event, object, open-issue, literature-coverage, provenance, and isolation summaries |
| Graph | Object relationships and the direct event history of each object |
| Timeline | Accepted events in order, including actor, function, and affected object |
| Issues | Current issues plus resolved, rejected, and `wont_fix` history |
| Evidence & Files | Citation verification, positioning coverage, Evidence -> SourceSpan -> Artifact chains, and file artifacts |
| Audit | Requested expert mode, actual backend, isolation status, and the action/function inventory |

The exporter also writes machine-readable data:

```text
visualization.json
story.json
events.json
objects.json
graph.json
literature.json
provenance.json
expert_executions.json
```

After a formal handoff, require acceptance before regenerating the canonical view:

```powershell
python scripts/export_project_visualization.py work/my-paper --require-accepted
```

## Core Concepts

| Concept | Meaning |
|---|---|
| Object | A semantic entity in the paper world, such as Claim, Evidence, Citation, or Issue |
| Artifact | A record of a real file or generated output, such as a PDF, extracted text, review report, or BibTeX file |
| SourceSpan | A reviewable text range inside an Artifact, with a locator and text hash |
| Link | An explicit relationship between objects, such as a Claim using Evidence |
| Action type | A business-level change proposed by an agent, such as `claim.created` |
| Function | The deterministic runtime capability that executes the change, such as `create_object` |
| Proposal | A structured state change that has not yet been committed |
| Event | An accepted, append-only fact recorded after validation |
| Projection | The current `paper.yml`, rebuilt by replaying the event log |
| Human gate | Explicit approval required for a high-impact action |

Object and Artifact are deliberately separate. A Claim is a semantic object; a `.tex` manuscript is an Artifact. Long text normally belongs in files referenced by Artifacts, not in event payloads or ordinary object fields.

## Three-Layer Architecture

### Semantic Layer

Defines what exists in the paper world:

- `ontology/objects.yml`: object types
- `ontology/properties.yml`: field types and enums
- `ontology/links.yml`: object relationships
- `ontology/constraints.yml`: cross-object constraints

Current object groups include:

```text
Core:        Paper, Section, Artifact, SourceSpan, Extraction
Literature:  SearchRun, ExternalWork, SearchResult, Citation
Argument:    Claim, Evidence, ReasoningStep
Experiment:  Method, Dataset, Experiment, Metric, Result
Review:      Review, Issue, Decision
Context:     Venue
```

### Kinetic Layer

Defines how the paper world can change:

- `kinetic/actions.yml`: allowed action types
- `kinetic/functions.yml`: deterministic runtime functions
- `kinetic/event_schema.yml`: the shared event envelope

`action_type` expresses business intent. `function` records the deterministic operation that carried it out. Each action declares a default function and an allowlist of valid functions.

### Dynamic Layer

Defines how agents route and perform work:

- `dynamic/router.md`: context-aware routing rules
- `dynamic/routing_policy.yml`: route-decision validation
- `dynamic/experts.yml`: expert registry
- `dynamic/workflows.yml`: workflow registry
- `dynamic/action_policy.yml`: evidence burden for proposals
- `dynamic/approval_policy.yml`: human gates
- `dynamic/invocation_policy.yml`: worker invocation modes

The router interprets research intent and emits a structured route decision. Scripts validate that decision; they do not pretend to infer research intent through keyword matching.

## Main Workflows

| Workflow | Purpose |
|---|---|
| `paper_intake` | Create a minimal paper project |
| `document_intake` | Normalize PDF, TeX, or Markdown into Artifact, Extraction, and SourceSpan records |
| `literature_intake` | Search for or import ExternalWork candidates and provider metadata |
| `literature_selection` | Verify candidates, create Citations, assign positioning roles, and connect Claims, Evidence, or Issues |
| `argument_extraction` | Extract Claims, Evidence, ReasoningSteps, Results, and support relationships |
| `positioning` | Assess gaps, contribution coordinates, competitors, and claim strength |
| `writing_revision` | Revise manuscript text against state, Issues, and venue constraints |
| `style_check` | Check expression, structure, and mechanical writing risks |
| `venue_fit` | Match venues, audiences, and formatting constraints |
| `mock_review` | Run independent reviewer packets and aggregate rejection risk |
| `rebuttal` | Map reviewer comments to evidence and response strategies |
| `manuscript_assembly` | Assemble the manuscript and run the submission-readiness gate |

## Research Integrity Gates

### Source provenance

The standard auditable source chain is:

```text
Evidence -> SourceSpan -> Artifact
```

A SourceSpan stores a locator, excerpt, and text hash. Experts judge whether a passage supports an Evidence object. Scripts verify that every referenced object exists and that the chain is complete.

### Literature verification

- `title_only` and `bibliographic` ExternalWork records are candidate leads.
- Their Citations must remain `tentative` and cannot enter Claim or Evidence support chains.
- A `verified` Citation requires auditable abstract or full-text metadata.
- Literature selection should cover predecessors, direct competitors, later extensions, and limitations.
- A missing role must become a targeted `citation_gap` Issue with `missing_literature_role` set explicitly.

### Expert isolation

An invocation packet records the requested execution mode. It does not prove that isolation occurred. Each completed run must record:

```text
requested_mode
actual_backend
isolation_verified
recorded_by
reason
```

`current_agent_fallback` must never be reported as an isolated worker.

### Human approval

Human confirmation is required by default for:

- changing the main Claim or contribution coordinate
- selecting or changing the target venue
- claiming new experiments or evidence
- ignoring a P0 Issue
- rejecting a reviewer request
- creating a checkpoint
- confirming final submission readiness

### Secret boundary

API keys, provider tokens, and personal contact details are runtime configuration, not paper state. Do not store secrets in:

```text
event logs
paper.yml
proposals.yml
Artifact content
handoff manifests
visualization JSON
Git
```

State should contain only a `secret_ref` or non-sensitive provider metadata. See `references/backend_secret_management.md` for the full policy.

## Common Commands

### State and events

```powershell
python scripts/event_log.py validate-log <project>/events/event_log.yml
python scripts/event_log.py project <project>/events/event_log.yml <project>/state/paper-replayed.yml
python scripts/checkpoint_event_log.py list <project>
python scripts/propose_event_revert.py <project> <event-id> --out revert-proposal.yml
```

### Documents and literature

```powershell
python scripts/extract_source_spans.py <project> <artifact-id> --out source-spans.yml
python scripts/fetch_search_results.py semantic_scholar "query" --limit 20 --out results.yml
python scripts/import_search_results.py <project> results.yml --out literature-intake.yml
python scripts/import_work_metadata.py <project> <external-work-id> metadata.yml --out metadata-proposals.yml
python scripts/validate_literature_coverage.py <project>
```

### Experts and review

```powershell
python scripts/validate_route_decision.py route_decision.yml
python scripts/prepare_expert_invocation.py <project> writing_expert --task "Revise the abstract."
python scripts/record_expert_execution.py <invocation-dir> --backend isolated_worker --recorded-by runtime
python scripts/prepare_review_run.py <project> --review-id RV-001 --runner-backend manual_packets
python scripts/aggregate_review_reports.py <project>/reviews/RV-001
```

### Output and handoff

```powershell
python scripts/export_tex_from_state.py <project> --append-event
python scripts/export_bib_from_state.py <project> --append-event
python scripts/validate_project_acceptance.py <project>
python scripts/handoff_project.py <project>
python scripts/export_project_visualization.py <project>
```

See [SKILL.md](SKILL.md) for runtime rules and [AGENTS.md](AGENTS.md) for development constraints.

## Repository Layout

```text
SKILL.md                 Agent entry point and runtime rules
AGENTS.md                Constraints for developers and coding agents
skill_manifest.yml       Package version, install mode, and required files

ontology/                Semantic Layer
kinetic/                 Kinetic Layer
dynamic/                 Dynamic Layer, experts, workflows, and templates
references/              Secret, venue, style, review, and assembly guidance
scripts/                 Validation, projection, intake, review, export, and handoff tools
tests/                   Unit, regression, and end-to-end tests
```

## Installation and Upgrades

Do not merge a new archive into an existing skill directory. Recursive copy operations can preserve stale files and produce a mixture of incompatible schemas and scripts.

Use the manifest-driven installer:

```powershell
python scripts/install_skill.py <target_skill_dir>
python scripts/install_skill.py <target_skill_dir> --replace
```

The default mode refuses to install over an existing target. `--replace` first creates a timestamped backup, then replaces the target with a complete staging copy validated against `skill_manifest.yml`.

## Verification Baseline

The `v0.2.2` release baseline is:

```text
61 tests passed
Semantic + kinetic + dynamic layer validation: ok
```

Key regressions covered by the suite include:

- project-relative PDF Artifact paths for external projects
- rejection of stale ExternalWork endpoints during dry-run
- acceptance of indirect Evidence -> SourceSpan -> Artifact provenance
- literature-verification and positioning-coverage gates
- honest recording of requested expert mode versus actual backend
- continuous event offsets and IDs, plus projection replay
- clean installation, manifest completeness, and static visualization export

Before committing or publishing, run the repository hygiene gate again:

```powershell
python scripts/check_repository_hygiene.py .
```

It rejects personal home directories, structured absolute paths, configured names, private-key headers, and common high-confidence API-token patterns. Use repeatable `--forbidden-name` arguments to block additional names or machine identifiers.

## Current Boundaries

This version is suitable for real-paper testing, internal demonstrations, and further product exploration. It should not yet be presented as a production multi-user backend.

Areas that still need broader validation include:

- very large event logs, long-lived checkpoints, and concurrent writes
- real remote isolated-worker scheduling
- rate limits, timeouts, and malformed responses across literature providers
- complete cross-platform regression coverage outside Windows

These limitations do not change the core contract: experts propose semantic judgments, deterministic scripts validate state changes, the event log preserves factual history, and humans own high-impact decisions.
