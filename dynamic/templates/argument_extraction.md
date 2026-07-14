# Argument Extraction Template

Use this template when the task is to split a section, draft, extracted text, or manuscript artifact into semantic paper objects.

## Scope

Input should be one or more existing objects or artifacts:

```yaml
paper_id: <paper id>
source_objects:
  - object_type: Section
    object_id: <section id>
source_artifacts:
  - artifact_id: <optional artifact id>
source_spans:
  - source_span_id: <optional source span id>
external_works:
  - external_work_id: <optional imported candidate work id>
```

## Extraction Pass

Fill this working table before writing proposals:

| Unit | Candidate object | Source span | Existing object? | Confidence | Notes |
|---|---|---|---|---|---|
| main claim | Claim | <sentence/paragraph> | <id or no> | high/medium/low | <why> |
| support fact | Evidence | <sentence/paragraph/table/citation> | <id or no> | high/medium/low | <why> |
| reasoning bridge | ReasoningStep | <implicit/explicit reasoning> | <id or no> | high/medium/low | <why> |
| empirical finding | Result | <number/table/finding> | <id or no> | high/medium/low | <why> |
| cited support | Citation | <citation key/title> | <id or no> | high/medium/low | <why> |
| imported candidate | ExternalWork | <search result/work id> | <id or no> | high/medium/low | <whether it should become a Citation> |
| missing support | Issue | <unsupported claim or broken link> | <id or no> | high/medium/low | <why> |

## Object Rules

- Create `Claim` only for statements the paper is actually making or clearly proposing.
- Create `Evidence` for concrete support: extracted text, user-provided facts, citations, examples, theorem/proof material, dataset facts, or experiment-result summaries.
- Evidence must be source-auditable. Prefer `references.source_span_ids` when the source text has already been split into `SourceSpan` objects. If support comes from an external webpage, paper, dataset, screenshot, search report, or generated file, create/link the relevant `Citation`, `ExternalWork`, or `Artifact`; do not leave the source only as prose in `source_ref`.
- If a relevant imported `ExternalWork` already exists, create a `Citation` only when the paper should actually cite it. The `citation.created` proposal should cite `references.external_work_ids`, then add a `citation_represents_external_work` link.
- Create `ReasoningStep` for proof steps, theoretical arguments, causal interpretations, conceptual bridges, or assumptions that connect evidence to a claim.
- Create `Result` only when the source contains an actual reported finding, numeric value, comparison, or qualitative result.
- Create `Issue` when a claim lacks support, support is ambiguous, or the extracted reasoning would require user confirmation.
- Do not invent citations, baselines, experiments, metrics, or results.
- Do not create Evidence whose main content is `[待补充]`, `待引用`, `TODO`, or another placeholder. Create an open Issue for missing evidence instead.

## Link Rules

Prefer explicit links over hiding relations in text fields:

```text
Section -> Claim: section_contains_claim
Claim -> Evidence: claim_supported_by_evidence
Claim -> ReasoningStep: claim_supported_by_reasoning_step
Claim -> Result: claim_supported_by_result
Claim -> SourceSpan: claim_anchored_to_source_span
Evidence -> Result: evidence_derived_from_result
Evidence -> ReasoningStep: evidence_derived_from_reasoning_step
Evidence -> SourceSpan: evidence_anchored_to_source_span
Citation -> ExternalWork: citation_represents_external_work
Issue -> target: issue_targets_object
```

Use `issue_targets_object` for the smallest object affected by an issue.

## Proposal Contract

Final output must be YAML proposals only:

```yaml
proposals:
  - action_type: claim.created
    payload:
      claim_id: C-example
      paper_id: P-example
      section_id: S-example
      text: "<claim text>"
      strength: moderate
      location_hint: "<source span>"
    references:
      source_span_ids:
        - SPAN-example-0001

  - action_type: evidence.created
    payload:
      evidence_id: E-example
      paper_id: P-example
      evidence_type: extracted_text
      summary: "<supporting fact>"
      source_ref: "Section S-example, paragraph 2"
    references:
      source_span_ids:
        - SPAN-example-0002

  - action_type: reasoning_step.created
    payload:
      reasoning_step_id: RS-example
      paper_id: P-example
      section_id: S-example
      claim_id: C-example
      reasoning_step_type: conceptual_link
      summary: "<why this evidence supports the claim>"

  - action_type: link.created
    payload:
      link_type: claim_supported_by_reasoning_step
      from_object_type: Claim
      from_object_id: C-example
      to_object_type: ReasoningStep
      to_object_id: RS-example

  - action_type: issue.created
    payload:
      issue_id: I-example-missing-support
      paper_id: P-example
      category: missing_evidence
      severity: P1
      issue_status: open
      target_object_type: Claim
      target_object_id: C-example
      section_id: S-example
      claim_id: C-example
      evidence: "<why the support is insufficient>"
      suggested_action: "<next concrete fix>"
```
