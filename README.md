# Mono assessment

Mick's take-home assessment for Mono, an AI startup.

**Status: planning only, no build yet.** The plan lives in the storytree project `mono-assessment`.

## Approach (from Mick, 2026-11-21)

- An AI-compiled audit checklist: an agent pulls the relevant documents together, assesses each against the
  assessment criteria, and outputs conclusions about the candidate. Each conclusion carries a source link back to its
  document.
- Deterministic checks against the criteria where possible. The model adds a one-sentence comment under an item where
  it finds something odd, quotes its source, and flags contradictions.
- First slice: mocked documents, all in one place, as a prototype that shows evidence. A full version would pull from
  SharePoint and the CRM.

The assessment brief (PDF) goes in [`brief/`](brief/).
