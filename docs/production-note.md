# Production note (first draft)

Status: a minimal first draft of Deliverable 3, for Mick to add to.

## What the first slice is

| Part | Here | In production |
|---|---|---|
| CRM, broker email | Mocked: folders of generated synthetic files | Read-only connectors into HarbourLine's systems |
| SharePoint documents | Generated PDFs in a local store (`document-store/`), read through mocked extraction records | A store in the Australian tenant, with a document reading service writing the records |
| Lending criteria | `checklist/criteria.py`, invented rules, versioned | HarbourLine's own rules, owned by credit policy |
| Model | Claude through the Anthropic API, behind `checklist/model.py`; tests replay saved responses | Claude on Amazon Bedrock in Sydney |
| Audit record | A file in `audit/` that each run adds a line to | The same, kept inside the Australian tenant |

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

1. A command that reruns the evaluation set against any model and reports accuracy.
2. Manual upload is built (`checklist upload`); next, a reading service for uploads, and uploads counting while
   SharePoint is down (open on the plan).
3. The tool drafts CRM updates for the analyst to accept; nothing is written automatically.
4. Key fields arriving already structured, so more items can be checked with the model off.
