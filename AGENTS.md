# Project Agent Instructions

## Runtime

- Run all Python commands through the project-local wrapper:

```powershell
.\scripts\run_python.cmd <script-or-module> [args]
```

- The wrapper resolves the interpreter from `PAPER_SUITE_PYTHON`, the active Conda environment, or the repo-local `.venv`.
- Do not commit machine-specific interpreter paths.
- Do not use `python`, `python3`, or the bundled Codex Python directly for this project unless the user explicitly overrides this instruction.
- PowerShell may print a `profile.ps1` execution-policy warning. Treat it as noise if the command exit code is 0.

## What This Project Is

This prototype is not "one more big research-writing prompt". It is a research paper workflow suite built around:

- a script-readable ontology,
- an append-only event log,
- a projected paper state,
- isolated expert workers,
- validated action proposals,
- and a thin `SKILL.md` entry point for agent platforms.

The core idea is:

```text
LLM experts make semantic judgments.
Hard scripts validate and commit state changes.
Event log is the source of truth.
paper.yml is only the current projection.
```

Do not collapse this back into a single giant prompt or a single mutable YAML state file.

## Layer Model

The project borrows a lightweight ontology framing:

```text
Semantic Layer
  What exists in the paper world.
  Files: ontology/objects.yml, ontology/properties.yml, ontology/links.yml, ontology/constraints.yml

Kinetic Layer
  How the paper world can change.
  Files: kinetic/actions.yml, kinetic/functions.yml, kinetic/event_schema.yml

Dynamic Layer
  How agents route work, invoke experts, and ask for human approval.
  Files: dynamic/router.md, dynamic/routing_policy.yml, dynamic/experts.yml,
         dynamic/workflows.yml, dynamic/approval_policy.yml,
         dynamic/invocation_policy.yml
```

This is an implementation choice for this suite, not a claim that every platform uses these exact three layers.

## Semantic Layer Principles

Semantic files define the domain model. They must stay machine-readable and conservative.

Use `ontology/objects.yml` for object types such as:

```text
Paper, Section, Claim, Evidence, Citation, Review, Issue, Decision, Venue,
Artifact, Method, Dataset, Experiment, Metric, Result, ReasoningStep
```

Use `ontology/properties.yml` for reusable enums and field vocabularies, such as:

```text
PaperStage, SectionType, IssueSeverity, ArtifactType, DecisionType,
MethodType, DatasetRole, ExperimentType, MetricDirection, ResultKind
```

Use `ontology/links.yml` for relationships between objects. Prefer explicit links over hiding important relations inside long text fields. Examples:

```text
Paper -> Section
Section -> Claim
Claim -> Evidence
Claim -> ReasoningStep
Claim -> Result
Review -> Issue
Issue -> Claim / Evidence / ReasoningStep / Method / Dataset / Experiment / Metric / Result
Decision -> Issue
Artifact -> Paper / Section / Review
```

Use `ontology/constraints.yml` for warning or blocking rules that scripts can check.

Important distinction:

```text
Object = semantic entity in the paper world.
Artifact = record of a real file or generated output.
artifact_type = subtype of Artifact, such as manuscript_tex or review_report.
```

Artifacts connect semantic state to filesystem reality. Do not put long generated manuscripts, review reports, or response letters directly inside ordinary object fields when a file artifact is more appropriate.

Issue targeting rule:

```text
Issue should target the smallest relevant semantic object.
Use target_object_type + target_object_id for new issue.created proposals.
review_id is provenance; it is not the issue target.
Paper-level issue targets are reserved for global concerns.
```

## Kinetic Layer Principles

Do not confuse `action_type` and `function`.

```text
action_type = business-level intent emitted by an agent or workflow.
function    = deterministic runtime capability that carries out or records that action.
```

For example:

```yaml
action_type: issue.created
function: create_object
object_type: Issue
```

`kinetic/actions.yml` defines which action types exist, what object/link they affect, and which functions are allowed to handle them.

`kinetic/functions.yml` defines deterministic capabilities such as:

```text
create_object
update_object
create_link
create_checkpoint
export_tex
prepare_review_run
aggregate_review_reports
```

An agent proposal may omit `function`; the runtime should use the action's `default_function`. If a proposal specifies a function, it must be listed in that action's `allowed_functions`.

## Event Log Rules

The event log is the source of truth.

```text
events/event_log.yml -> scripts/event_log.py project -> state/paper.yml
```

Rules:

- Events are append-only.
- Offsets start at 1 and must be continuous.
- Event IDs follow the current `EVT-000001` style.
- Experts and workers must not directly edit `state/paper.yml`.
- Workers produce `proposals.yml`; the main runtime validates and appends events.
- `paper.yml` is a projection and may be regenerated from the event log.

Checkpointing is allowed, but it must preserve auditability:

```text
checkpoint.created
  -> points to a human-approved state snapshot
  -> archives the previous active log
  -> starts a shorter active log from the checkpoint
```

Do not implement compaction by deleting history.

## Dynamic Layer Principles

The suite uses one skill with multiple expert files, not many independent Codex skills.

Rationale:

- shared ontology and action contracts stay consistent,
- state transfer is cleaner,
- platform migration is easier,
- expert prompts are loaded on demand instead of all at once.

Current expert set:

```text
positioning_expert
writing_expert
style_expert
venue_expert
review_expert
rebuttal_expert
assembly_expert
```

Each expert should have:

- a narrow responsibility boundary,
- explicit input objects/artifacts,
- allowed output action types,
- human-gate rules where needed,
- a compact proposal fixture in the expert brief, template, or focused test,
- and a dry-run validation path through `apply_action_proposals.py`.

Expert files are not historical notes. Do not mention "the old research-writing skill" inside files intended for future agents. They should be self-contained operating instructions.

## Invocation Model

Do not assume "expert" means "new agent" in every case.

The current intended model is:

```text
Current/main agent
  -> routes request
  -> prepares isolated worker packet
  -> receives report/proposals
  -> validates proposals
  -> appends event log
```

Formal single-expert execution should default to `isolated_worker`, because prompt context cannot truly be unloaded from a long-running agent conversation.

Review is the main case for true multi-agent execution:

```text
methodologist reviewer
domain expert reviewer
general reviewer
AC aggregator
```

Reviewer workers must read the same frozen snapshot, avoid seeing each other's outputs, and write only role outputs. The AC aggregator creates final proposals, which are then committed through the normal event log path.

## Routing Model

Do not build a keyword-only router.

The router should be an LLM context-wise decision that outputs a structured route decision. Scripts validate the decision; scripts do not pretend to understand the user's research intent.

Expected route decision shape:

```text
workflow
primary_expert
invocation_mode
allowed_actions
required_state
required_artifacts
human_gates
```

Validation belongs in `scripts/validate_route_decision.py`.

## Writing New Ontology / Workflow Pieces

When adding a new capability, follow this order:

1. Decide whether the concept is an object, artifact type, link type, action type, function, workflow, expert rule, or template.
2. Add semantic vocabulary only if the state really needs to remember it.
3. Add action types only if an agent/workflow needs to propose that change.
4. Add functions only for deterministic work that scripts can actually perform.
5. Add or update an expert brief only for semantic judgment, writing judgment, or workflow-specific instructions.
6. Add a small example proposal or fixture.
7. Run validation.

Useful validation commands:

```powershell
.\scripts\run_python.cmd scripts\validate_layers.py
.\scripts\run_python.cmd scripts\check_repository_hygiene.py .
.\scripts\run_python.cmd scripts\event_log.py validate-log <project_dir>\events\event_log.yml
```

Prefer small, testable additions. Do not turn the ontology into a list of every academic concept anyone can name.

## Long Text Policy

Long text should normally live in artifacts.

Use object fields for identifiers, summaries, status, structured metadata, and short content. Use artifacts for:

```text
manuscript drafts
section drafts
review reports
aggregate review reports
response letters
positioning cards
venue cards
style reports
LaTeX outputs
PDF outputs
```

This keeps event payloads small and replayable.

## Raw Document Intake

Do not let writing/review/style experts freely parse raw PDF/DOCX/image inputs.

Raw documents should first go through the controlled `document_intake` workflow:

```text
source PDF/DOCX/image
  -> source artifact
  -> extracted_text_md when available
  -> extraction_report artifact
  -> Extraction object
  -> extraction_risk Issue if extraction is missing or uncertain
```

Use `scripts/ingest_pdf_project.py` for the first PDF-only implementation. Downstream experts should read `paper.yml`, `extracted_text_md`, and `extraction_report`, then flag extraction gaps as issues instead of silently trusting raw PDF parsing.

## Human Gates

Do not let agents silently decide high-impact research actions.

Human approval is expected for:

- changing the main claim or contribution coordinate,
- selecting or changing target venue,
- ignoring P0 issues,
- rebuttal strategies such as rejecting a reviewer request,
- claiming new experiments or evidence,
- checkpoint creation,
- final submission readiness.

Represent these as `decision.proposed` or related decision actions, then let the user confirm.

## Current Design Motivation

The original problem was not that a large research-writing prompt had no useful content. It had useful stage outputs and reusable materials. The problem was that those outputs were mostly human-readable documents, not structured state.

This suite tries to upgrade:

```text
stage md files
  -> object / artifact / issue / decision records

prompt-driven flow
  -> route decisions + invocation packets + proposal contracts

chat memory
  -> event log + checkpoint + replayable state
```

Keep that distinction in mind when changing the system. The goal is not to make prompts longer. The goal is to make research workflows auditable, recoverable, and easier to iterate.
