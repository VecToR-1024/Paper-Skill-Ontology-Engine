# Core Hardening v0.2

## Purpose

Before turning the suite into a frontend/backend product, stabilize the core action system. The frontend should eventually let users edit a paper graph, but the backend must still accept only validated, append-only actions.

## Product Direction

The long-term product shape is:

```text
User graph UI
  -> UI intent
  -> validated action proposal
  -> action gate / human approval
  -> append-only event log
  -> projected state
  -> AI checks and visualization
```

Do not expose action types and functions as the normal user model. Keep them in audit/debug views.
Secrets are runtime configuration, not project state; see `references/backend_secret_management.md`.

## Hardening Order

0. Backend secret management boundary.
1. Semantic revert / undo for committed events.
2. Artifact, source, citation, and evidence acceptance rules.
3. User view vs audit view vs debug view separation.
4. Regression fixtures for representative projects.
5. Read-only frontend split: data builder plus static frontend.
6. Editable frontend intent contracts.

The editable frontend contract comes late because it should be shaped by real UI interactions, not guessed too early.

## Backend Secret Boundary

API keys and provider credentials must never enter event logs, projected state, proposals, artifacts, visualizations, handoff manifests, or committed files. Project state may store `provider`, `model`, and `secret_ref`, but not raw secret values.

```text
allowed:
  provider: openai
  model: gpt-5
  secret_ref: local:user-default-openai

forbidden:
  api_key: sk-...
  Authorization: Bearer ...
```

The future backend should expose a settings surface for submitting keys into a secret store. The action runtime and AI runtime should pass `secret_ref` through normal project records and resolve the secret only at call time.

## Semantic Revert Rule

Committed events are not deleted, edited, or renumbered. Reverting a committed change means appending a new compensating action.

```text
bad:
  delete EVT-000041
  edit EVT-000041
  rewrite offsets

good:
  generate a proposal that restores the affected object fields
  validate it through apply_action_proposals.py
  append the approved compensating event
```

The first implemented slice is `scripts/propose_event_revert.py`:

- supports update/upsert object events only;
- restores fields changed by the target payload;
- handles `issue.severity_changed` as a compensating reclassification that restores current `severity`;
- refuses fields that did not exist before the target event;
- refuses by default when later events changed the same object fields;
- writes proposals instead of mutating state directly;
- keeps high-impact action approval gates intact.

Regression coverage now checks:

- `claim.updated` revert generation, dry-run, human-gate blocking, and approved apply;
- `issue.status_changed` revert to the previous workflow status;
- `issue.severity_changed` revert to the previous current severity;
- `section.upserted` revert without a human gate;
- conflict rejection when later events changed the same object field;
- explicit rejection of object-creation reverts in this slice.

Future revert work should add:

- explicit support for object creation reverts;
- explicit support for link create/remove inverses;
- a clean field-unset mechanism if object updates need to remove fields;
- UI affordances such as `Undo this event` in object history.

## Artifact / Source Acceptance Rule

Formal handoff output is stricter than "a file exists somewhere" or "the agent mentioned a source in prose." `scripts/validate_project_acceptance.py` now rejects:

- durable files under `artifacts/` or `outputs/` that are not recorded as `Artifact` objects;
- `Artifact` objects whose `path` does not point to an existing file;
- `Evidence` with placeholder text such as `[待补充]`, `TODO`, `<citation>`, or `<source>`;
- `Evidence.artifact_id` values that do not resolve to existing `Artifact` objects;
- external `Evidence.source_ref` strings with no `artifact_id` and no `evidence_uses_citation` link;
- `evidence_uses_citation` links pointing to missing `Citation` objects;
- `Citation` objects that are not traceable through a URI or enough bibliographic metadata.

This keeps decorative previews, invented source strings, and empty citation shells out of formal project handoff. If an agent wants a user-facing HTML overview, it must create a real file and propose an `artifact.created` event with `artifact_type: preview_html`.

`scripts/export_bib_from_state.py` closes the reverse citation path: project ingest can already turn `.bib` into `Citation` objects, and assembly can now turn `Citation` objects back into a `bibliography_bib` Artifact. This prevents the system from having structured citations in state but no deliverable `.bib` file.

## Frontend Boundary

The current visualization is not yet a frontend/backend app. It is a static exporter with a useful internal split:

```text
build_project_data()
  -> visualization.json
  -> static HTML/JS rendering
```

`scripts/export_project_visualization.py` and `scripts/handoff_project.py` both write `visualization.json` as the complete render-data bundle, alongside smaller `events.json`, `objects.json`, `graph.json`, and `story.json` slices.

The static page now uses hash-routed pages (`#overview`, `#graph`, `#timeline`, `#issues`, `#evidence-files`, `#audit`) instead of one long scroll. This is still a static export, but it gives the eventual frontend split a route boundary to preserve.

The next safe frontend step is to separate `build_project_data()` from the HTML/JS assets. A real editable API should wait until action, revert, artifact/source, and view-layer boundaries are stable.

The static Object Link Graph now exposes read-only per-object event history in the selected-object detail panel. This gives future undo/edit UI a natural audit anchor without making action types the user's primary model.

## User / Audit View Boundary

The visualization now keeps the normal reading path focused on paper concepts:

```text
Project Tracking Model
Object Link Graph
Change Timeline
Open Review Issues
Evidence Trail
Project Files & Artifacts
```

`Action Type / Function Inventory` lives under a collapsed `Audit / Debug Details` section. This satisfies workflow audit needs without teaching ordinary users that action types and runtime functions are the product's primary mental model.
