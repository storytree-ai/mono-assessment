# Production note (first draft)

Status: a minimal first draft of Deliverable 3, for Mick to add to.

## What the first slice is

| Part | Here | In production |
|---|---|---|
| CRM, broker email | Mocked: folders of generated synthetic files, pulled by connectors into the local cache | Read-only connectors into HarbourLine's systems |
| SharePoint documents | Generated PDFs in a mocked SharePoint (`sharepoint/`), pulled into a run-scoped local cache (`cache/`) and read through mocked extraction records | A cloud bucket in the Australian tenant as the cache, with an extraction service (for example Amazon Textract or Azure Document Intelligence) writing the records |
| Lending criteria | `checklist/criteria.py`, synthetic policy, versioned keys | HarbourLine's own mandatory-evidence rules, owned by credit policy |
| Model | Claude through the Anthropic API, behind `checklist/model.py`; tests and the default run replay saved responses | Claude on Amazon Bedrock in the Sydney region (below) |
| Audit record | Append-only JSON lines in `audit/` | An append-only store inside the Australian tenant |

## Target architecture and data flow

Documents, the CRM record and broker emails are gathered into one store. The model pulls out each value with a pointer
to where it found it. Fixed rules check those values and set each item's state. The analyst reads the checklist.

## Identity, access, privacy and audit controls

Personal data stays in HarbourLine's Australian tenant: in production the model runs on Bedrock in Sydney, a config
change. The tool is read-only. Every run records the model, the sources and the rule versions used. Who can see what:
To confirm with Mick.

## Evaluation dataset and acceptance criteria

Start with the two test applications and their expected results; add every failing case found in use. Rerun the set
on any new model before switching. HarbourLine's target is at least 95% accuracy on mandatory evidence.

## Model and system failure modes, and safe fallback

- Model down or not allowed: the fixed checks still run, and document items say "unable to verify" with links.
- A source system down: those items say so, and the rest of the checklist still progresses.
- An unreadable document: "unable to verify", for the analyst to check by hand, not counted as missing.
- The model can raise a concern on an item, but never clear one.

## Pilot, human review and rollout sequence

The analyst reviews every item and the credit officer makes every decision. The rollout order: To confirm with Mick.

## Monitoring, incident response and rollback

Each run's record shows what the tool showed and why. If an error is found after use, treat it like a recall: apply
HarbourLine's process for analyst mistakes to every application it touched, fix it, and add the case to the
evaluation set. Rollback is switching the model off or changing it in config.

## Analyst adoption and feedback loop

Aim at the steps analysts find most painful (discovery question 2). HarbourLine's target is 70% weekly use in the
pilot group. Tell analysts plainly when something is paused. How feedback is collected: To confirm with Mick.

## Build, buy or reuse

Buy or reuse: the model (Claude on Bedrock), a document reading service (for example Amazon Textract or Azure
Document Intelligence), and HarbourLine's own CRM and SharePoint. Build: the lending rule checks and the checklist.
To confirm with Mick.

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
