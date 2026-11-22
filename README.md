# Mono assessment

Mick's take-home assessment for Mono, an AI startup.

**Status: first slice built, with the fixes from Mick's review of it, for his review.** The plan lives in the storytree project `mono-assessment`.

## Problem and release brief (first draft)

### Outcome (provisional, to be finalised after Mick's build review)

Analysts spend less time chasing missing, expired or contradictory evidence. Each flagged application comes with a
checklist that shows where each finding came from, so the analyst starts from a short list of problems, not a pile of
documents. The analyst and the credit officer still make every decision.

### Discovery: five questions before committing

1. What extra work and frustrations did the two previous pilots create for analysts?
2. Where does analysts' time go, and which steps frustrate them most, ranked? Fixing their worst pain is what wins
   their support and use.
3. What are the sponsor's goals, why was this process chosen, and how does it fit the company's wider goals?
4. Who must sign off and buy in, credit officers included?
5. Can a privacy or compliance person join the project to agree how personal data is used (past cases for testing,
   which model services)?

### Scope

In: steps 2 to 5 of the current workflow. The tool reads an application's documents, CRM record and broker emails,
checks them against the lending criteria, and lists what is missing, expired or contradictory, each with its source.
It gives the analyst a short exception brief, keeps a record of every run, takes manual uploads, and still works
with the model switched off.

Out: approving or declining credit, recording the credit officer's decision (step 7), any write to the CRM, and real
connections to HarbourLine's systems (all mocked here).

### Assumptions

- All data here is made up. The CRM, SharePoint and broker emails are mocked, with the documents in one place.
- We do not know which CRM HarbourLine uses; we assume it is Salesforce-like, as the brief says.
- Which criteria apply to a loan can be set in advance as fixed rules. The criteria here are invented; HarbourLine's
  credit policy team would own the real ones.
- A document reading service turns documents into fields. The prototype uses ready-made records and never reads a
  PDF itself.
- Claude on Amazon Bedrock in Sydney would be an approved model service, keeping personal data in Australia.
- Two test applications are enough to show the flow.

### Success evidence

To be written after Mick's build review.

## Approach (from Mick, 2026-11-21)

- An AI-compiled audit checklist: an agent pulls the relevant documents together, assesses each against the
  assessment criteria, and outputs conclusions about the candidate. Each conclusion carries a source link back to its
  document.
- Deterministic checks against the criteria where possible. The model adds a one-sentence comment under an item where
  it finds something odd, quotes its source, and flags contradictions.
- First slice: mocked documents, all in one place, as a prototype that shows evidence. A full version would pull from
  SharePoint and the CRM.

The assessment brief (PDF) goes in [`brief/`](brief/).

## Run it

Python 3.12. Everything under `applications/` and `sharepoint/` is generated synthetic data.

```sh
python3 -m venv .venv            # on a box without ensurepip: python3 -m venv --without-pip .venv, then get-pip.py
.venv/bin/python -m pip install -e . pytest     # installs the checklist command into .venv
.venv/bin/python -m pytest       # no model is called, no API key needed
source .venv/bin/activate        # then checklist is one word

checklist                                                     # the pending applications
checklist app-1001 --as-of 2026-11-22                         # open one: a run; replays the saved model responses
checklist app-1001 --as-of 2026-11-22 --details               # adds the run id, model, criterion versions and documents
checklist app-1002 --as-of 2026-11-22
checklist app-1001 --model none                               # the no-model mode
checklist app-1001 --simulate-outage sharepoint               # a source down: upload a document at the prompt
checklist app-1001 --model anthropic                          # a real call (ANTHROPIC_API_KEY)

checklist documents app-1001                                  # what the cache holds for an application, by run
```

Opening an application starts a run with its own id. The run drops cache entries older than `retention_days`
(`[cache]` in `config.toml`, 14), then each source connector (`checklist/connectors.py`: the CRM, SharePoint and broker
email, all mocked) pulls into the local cache, `cache/<application id>/`, a folder standing in for a cloud bucket.
At a terminal, the run then lists what it fetched and offers to upload more documents: a file path, then its kind and
where it came from. The checklist reads only the cache, and only what this run put there: every file carries the
run's id in its origin record, and anything from an earlier run is stale and reads as if it were not there. So
`--simulate-outage sharepoint` stops only the SharePoint pull: a document uploaded in this run is still read, and an
item with nothing in this run's cache reads unable to verify (source unavailable). Uploads are not carried to the
next run; upload again in each run while SharePoint is down. The audit record names the run id.

The SharePoint documents are generated PDFs in the mocked SharePoint, `sharepoint/<application id>/`. Each sits
beside a record of where it came from (`.origin.json`) and a mocked extraction record (`.extraction.json`), and the
connector caches all three; the checklist reads the extraction through `checklist/cache.py`, the mocked document
API, and never parses a PDF. That record is where a real extraction service would plug in. An uploaded document has
no extraction record, so it reads "awaiting extraction". `python3 scripts/make_documents.py` regenerates the PDFs
from the extraction records, with no extra library. On a terminal, each source is a clickable link to its cached file.

Each item reads as its rule, its state, the finding, the recommended action and the sources. The checklist prepares
evidence for the analyst and credit officer; it never approves or declines credit (`checklist --help` says so too).
`--save-responses` with `--model anthropic` saves the real responses over the hand-written ones. Every run appends a line to
`audit/audit.jsonl`. The provider and model are set in `config.toml`. Next steps are in
[`docs/production-note.md`](docs/production-note.md); the COO update and harvest bullets are in
[`docs/client-update.md`](docs/client-update.md).

| Folder | What it is |
|---|---|
| `checklist/criteria.py` | The versioned lending criteria and their deterministic checks |
| `checklist/engine.py` | A run: pull, offer uploads, then extract, decide, annotate, report, audit |
| `checklist/connectors.py` | The source connectors (CRM, SharePoint, broker email, all mocked) that fill the cache |
| `checklist/cache.py` | The local cache and the mocked document API over it: put, read this run's, prune, upload |
| `checklist/model.py` | The one model wrapper: anthropic, replay or none |
| `sharepoint/` | The mocked SharePoint: generated PDFs, their origin and mocked extraction records |
| `scripts/make_documents.py` | Renders the stored documents as PDFs from their extraction records |
| `prompts/` | The two prompts the model gets |
| `applications/` | The two mocked applications, their saved model responses and expected reports |
