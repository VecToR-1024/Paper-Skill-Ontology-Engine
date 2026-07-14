# Issue Targeting v0.2

## Purpose

Issues should identify the smallest semantic object that is actually at risk. A paper-level issue is still allowed, but it should be reserved for global concerns such as overall positioning, submission readiness, or manuscript-wide structure.

## Standard Fields

New `issue.created` proposals should include:

```yaml
target_object_type: Claim
target_object_id: C-main-claim
```

Allowed target types are:

```text
Paper, Section, Claim, Evidence, ReasoningStep, Method, Dataset,
Experiment, Metric, Result, Citation, Venue, Extraction, Artifact
```

`review_id` is provenance: it records which review produced or motivated the issue. It is not the target object.

## ReasoningStep

Use `ReasoningStep` for proof steps, theoretical arguments, conceptual links, causal interpretations, or other explicit reasoning units. For empirical papers, this avoids overusing the narrower word "Proof"; for formal papers, `reasoning_step_type: proof_step` can represent proof structure.

## Migration Rule

Legacy fields remain valid during migration:

```yaml
section_id: S-abstract
claim_id: C-main-claim
review_id: R-style-001
```

When only `claim_id` exists, tooling may infer `target_object_type: Claim`. When only `section_id` exists, tooling may infer `target_object_type: Section`. New expert outputs should write the target fields directly.
