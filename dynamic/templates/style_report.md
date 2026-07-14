# Style Report

review_id: <review id>
paper_id: <paper id>
scope: whole_paper | section | paragraph | quick_scan_interpretation

## Inputs
- sections: <section ids>
- artifacts: <artifact ids>
- claims: <claim ids>
- quick_scan_report: <artifact id or none>

## Top Risks
- severity: P0 | P1 | P2
  category: style_violation | overclaim | missing_evidence | unclear_contribution
  location: <section / claim / paragraph>
  evidence: <what the expert observed>
  suggested_action: <what writing_expert or user should do>

## Mechanical Checks
- <script finding or N/A>

## Semantic Checks
- sentence_claim_load: <summary>
- paragraph_argument: <summary>
- claim_evidence_alignment: <summary>
- section_boundary: <summary>

## Handoff
- writing_expert: <revision notes>
- review_expert: <risks worth cold-reading>
