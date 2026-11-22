# Production note: next steps (draft, first slice)

Status: a short note from the build session (2026-11-22), not the brief's full one-page Deliverable 3. Who writes
that in full is open on the plan (question_f2bf84606c30).

## What the first slice is

| Part | Here | In production |
|---|---|---|
| CRM, SharePoint, broker email | Mocked: folders of generated synthetic files | Read-only connectors into HarbourLine's systems |
| Lending criteria | `checklist/criteria.py`, synthetic policy, versioned keys | HarbourLine's own mandatory-evidence rules, owned by credit policy |
| Model | Claude through the Anthropic API, behind `checklist/model.py`; tests and the default run replay saved responses | Claude on Amazon Bedrock in the Sydney region (below) |
| Audit record | Append-only JSON lines in `audit/` | An append-only store inside the Australian tenant |

## Production target: Claude on Amazon Bedrock in Sydney

The brief requires personal data to stay in HarbourLine's Australian tenant and raw customer data never to reach an
unapproved external endpoint. The prototype sends only synthetic data to the Anthropic API. In production the same
wrapper takes a Bedrock provider pointed at `ap-southeast-2` (Sydney) in HarbourLine's own AWS account, so documents
never leave the tenant; the provider stays one config setting, so a privacy ruling against an endpoint is a config
change plus a rerun of the evaluation set, with the no-model mode covering the gap.

## Next steps, not built in this slice

1. **Evaluation-set rerun command.** One command that reruns every saved case (starting with the two applications
   here) against any provider and model and reports extraction accuracy against the expected reports, so a new
   model is judged in minutes; every failing case found in use is added to the set (ADR-0001, twists 1, 2 and 5).
2. **Manual upload path.** A way for an analyst to add a document fetched by hand when a source system is down,
   recording where it came from (uploaded by whom, when, from where), so the checklist still progresses while the
   document API is unavailable (twist 4).
3. **CRM-update draft with approval.** The tool drafts the CRM update (for example the exception summary) for the
   analyst to accept after review; nothing is written automatically, keeping the release read-only and every write
   human-approved (twist 3).
4. **Structured sidecar for the no-model mode.** Documents arriving with their key fields already structured (from a
   document API or the upload form: licence expiry, invoice total), so more items are decided with the model off;
   today those items read "unable to verify (model unavailable)" with links (question_b9e15794f3c0, option 2).
