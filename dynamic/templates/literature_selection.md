# Literature Selection Template

Use this template after `literature_intake` has already created `SearchRun`, `ExternalWork`, and `SearchResult` objects.

## Scope

Input should include existing paper objects and imported candidate works:

```yaml
paper_id: <paper id>
target_objects:
  - object_type: Claim
    object_id: <claim needing positioning/support>
external_works:
  - external_work_id: <candidate work id>
search_runs:
  - search_run_id: <optional search run id>
```

## Selection Pass

Fill this working table before writing proposals:

| ExternalWork | Metadata quality | Use decision | Citation role | Positioning role | Target object | Reason | Risk / uncertainty |
|---|---|---|---|---|---|---|---|
| <id/title> | title_only / bibliographic / abstract / full_text | cite / reject / hold | background / support / contrast / limitation / method_source / dataset_source | predecessor / direct_competitor / later_extension / limitation / background / unknown | <Claim/Evidence/Section id> | <why> | <what still needs checking> |

## Object Rules

- Do not create new `ExternalWork`, `SearchRun`, or `SearchResult` objects here. Those belong to `literature_intake`.
- Create `Citation` only for imported works the paper should actually cite.
- A `citation.created` proposal selected from search must include `references.external_work_ids`.
- Set `verification_status: verified` only when the linked ExternalWork has `metadata_quality: abstract` or `full_text`. Otherwise set `tentative`.
- A tentative Citation may link to its ExternalWork, but must not use `claim_uses_citation` or `evidence_uses_citation` until metadata is enriched and the Citation is verified.
- Do not treat a search hit as evidence by itself. Link the selected `Citation` to a `Claim` or `Evidence`, or create an `issue.created` when the relationship still needs user/expert confirmation.
- Do not invent bibliographic metadata that is missing from the ExternalWork. If a key field is missing, create an issue or leave a conservative Citation payload.
- Every `citation_gap` Issue must set `target_object_type` and `target_object_id`; use `Paper` only for a genuinely project-wide coverage gap.
- Before finishing selection, run `scripts/validate_literature_coverage.py`. Cover predecessor, direct competitor, later extension, and limitation, or create one targeted open `citation_gap` Issue per missing role using `missing_literature_role`.

## Link Rules

Use explicit links:

```text
Citation -> ExternalWork: citation_represents_external_work
Claim -> Citation: claim_uses_citation
Evidence -> Citation: evidence_uses_citation
Issue -> target: issue_targets_object
```

## Proposal Contract

Final output must be YAML proposals only:

```yaml
proposals:
  - action_type: citation.created
    payload:
      citation_id: Cite-example
      paper_id: P-example
      citation_key: example2026
      title: "<title copied from ExternalWork>"
      authors: "<authors copied from ExternalWork when present>"
      year: 2026
      uri: "<stable uri or doi url when present>"
      role: background
      verification_status: verified
      positioning_role: predecessor
    references:
      external_work_ids:
        - EW-example

  - action_type: link.created
    payload:
      link_type: citation_represents_external_work
      from_object_type: Citation
      from_object_id: Cite-example
      to_object_type: ExternalWork
      to_object_id: EW-example

  - action_type: link.created
    payload:
      link_type: claim_uses_citation
      from_object_type: Claim
      from_object_id: C-example
      to_object_type: Citation
      to_object_id: Cite-example
```
