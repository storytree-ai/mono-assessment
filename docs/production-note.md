# Production note: next steps (draft, first slice)

Status: a short note from the build session (2026-11-22), not the brief's full one-page Deliverable 3. Who writes
that in full is open on the plan (question_f2bf84606c30).

## What the first slice is

| Part | Here | In production |
|---|---|---|
| CRM, broker email | Mocked: folders of generated synthetic files, pulled by connectors into the local cache | Read-only connectors into HarbourLine's systems |
| SharePoint documents | Generated PDFs in a mocked SharePoint (`sharepoint/`), pulled into a run-scoped local cache (`cache/`) and read through mocked extraction records | A cloud bucket in the Australian tenant as the cache, with an extraction service (for example Amazon Textract or Azure Document Intelligence) writing the records |
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
2. **Manual upload path: now built** (ADR-0004, ADR-0005). Opening an application starts a run that offers an
   upload after its pull; the upload goes into the run's cache, records where it came from (by whom, when, from
   where) and is read while SharePoint is down (twist 4); it reads "awaiting extraction". Next: an extraction
   service writing those records, and carrying uploads forward between runs (today they are re-uploaded each run).
3. **CRM-update draft with approval.** The tool drafts the CRM update (for example the exception summary) for the
   analyst to accept after review; nothing is written automatically, keeping the release read-only and every write
   human-approved (twist 3).
4. **Structured sidecar for the no-model mode.** Documents arriving with their key fields already structured (from a
   document API or the upload form: licence expiry, invoice total), so more items are decided with the model off;
   today those items read "unable to verify (model unavailable)" with links (question_b9e15794f3c0, option 2).
