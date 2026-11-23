# Mono assessment

Mick's take-home assessment for Mono: an audit checklist prototype for HarbourLine Finance's loan-application exception
triage. All data here is fictional. The assessment brief is in [`brief/`](brief/).

## Problem and release brief

### Outcome

Analysts spend less time chasing missing, expired or contradictory evidence. Each flagged application arrives with a
checklist of what is missing, out of date or inconsistent, each finding pointing to its source, so the analyst starts
from a short list of problems rather than a pile of documents. The analyst and the credit officer still make every
decision. For HarbourLine, that means a smaller backlog and less rework from missed evidence.

### Discovery: five questions before committing

1. What extra work and frustrations did the two previous pilots create for analysts?
2. Where does analysts' time go, and which steps frustrate them most, ranked? Fixing their worst pain is what wins
   their support and use.
3. What are the sponsor's goals, why was this process chosen, and how does it fit the company's wider goals?
4. Who must sign off and buy in, credit officers included?
5. Can a privacy or compliance person join the project to agree how personal data is used (past cases for testing,
   which model services)?

### Scope

In: steps 2 to 5 of the current workflow, and a draft of step 6's exception brief. The tool reads an application's
documents, CRM record and broker emails, checks them against the lending criteria, and lists what is missing, expired
or contradictory, each with its source. It gives the analyst a short exception brief, keeps a record of every run,
takes manual uploads, and still works with the model switched off.

Out: approving or declining credit, recording the credit officer's decision (step 7), any write to the CRM, and real
connections to HarbourLine's systems (all mocked here).

### Assumptions

- The CRM, SharePoint and broker emails are mocked as folders of generated files.
- HarbourLine's CRM is Salesforce-like, as the brief says.
- Which criteria apply to a loan can be set in advance as fixed rules. The criteria here are invented; HarbourLine's
  credit policy team would own the real ones.
- A document parser turns documents into fields. The prototype uses ready-made records and never reads a
  PDF itself.
- Claude on Amazon Bedrock in Sydney would be an approved model service, keeping personal data in Australia.
- Two test applications are enough to show the flow.

### Success

The pilot is working when, for the pilot analyst group:

- preparation time is under 10 minutes per application (32 today);
- mandatory evidence is extracted with at least 95% accuracy on an agreed test set;
- nothing is written to a system of record without approval;
- every statement in a brief traces to its source, or is marked unable to verify;
- at least 70% of the pilot analysts use it each week (38% use today's tool);
- the time saved supports a defensible annual value: 22 minutes saved on 240 applications a day is 88 analyst hours
  a day, about 22,000 hours a year (assuming 250 working days, and the time going to the backlog).

## How it works

Every checklist item is keyed to a versioned lending criterion, and a fixed function decides it: satisfied, exception
(missing, expired or inconsistent) or unable to verify (for example, a source down or a document unreadable). The
model only pulls values out of documents, each with a quote and a pointer to where it found it, and adds a finding and
a recommended action to items that failed or could not be checked. It can raise a concern that turns a satisfied item
into an exception, but it can never clear one; both its call and the function's are kept in the audit record. Each run
reads only the documents it fetched, so the checklist always reflects the current sources. Errors pass up in
layers: each layer passes up the error it has (a document the parser cannot read stays unable to verify, saying
why), a layer with no answer from the one below reports it unavailable, and a top-level classifier turns whatever
comes up into a plain status or a plain system error, never a traceback.

## What the prototype shows

On the two synthetic applications (20 tests, `pytest`):

- APP-1001: the expired driver's licence, the dealer invoice that is $15,000 below the CRM loan amount, and the missing
  second year of financials are each an exception, each with a quote from and a link to its source.
- APP-1002: the corrupted bank statement reads unable to verify, for the analyst to check by hand, not missing.
- Each application's checklist matches its saved expected report; with the model's responses replayed, every run
  gives the same checklist.
- A model concern raises a satisfied item to an exception and never clears one, and a model quote not found in its
  source document makes the item unable to verify ("please check").
- One live run (2026-11-23): Claude Opus 5.5 through Claude Code's own login (`--model claude-code`, which calls
  `claude -p`; no API key) gave both applications exactly their expected checklists, every quote found in its source.
  Its responses are in `applications/*/live-responses/`; the replayed `model-responses/` are hand-written.
- With the model off, the CRM checks are still decided and the document items are listed with links; with SharePoint
  down, its items read unable to verify, never missing, and a document uploaded in the run is still read: the same
  path covers a source whose access is delayed by up to a week.

## What was prioritised, what remains, what next

Prioritised, within the two-hour timebox: one narrow, explainable slice (the evidence checklist), with its safeguards
built in from the start: source pointers, the audit record, safe fallbacks when a model or source is down, and manual
upload.

What remains, and next:

1. **No measurements yet.** Next: evaluate on HarbourLine's historical cases against the 95% extraction target, once
   privacy agrees how that data may be used.
2. **Security hardening is not done.** Next: an adversarial security review covering identity and access (OAuth/OIDC)
   and tokenising or hashing personal data. It was left out deliberately to respect the timebox.

The production path is in [`docs/production-note.md`](docs/production-note.md).

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
checklist app-1001 --as-of 2026-11-22 --model none            # the no-model mode
checklist app-1001 --as-of 2026-11-22 --simulate-outage sharepoint   # a source down: upload a document at the prompt
checklist app-1001 --as-of 2026-11-22 --model anthropic       # a real call (ANTHROPIC_API_KEY)
checklist app-1001 --as-of 2026-11-22 --model claude-code     # a real call through Claude Code's login (claude -p)

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
connector caches all three; the checklist reads the extraction through `checklist/cache.py`, the mocked document API,
and never parses a PDF. That record is where a real document parser would plug in. An uploaded document has no parser
output, so it reads unable to verify (document parser unavailable). `python3 scripts/make_documents.py` regenerates
the PDFs from the extraction records, with no extra library. On a terminal, each source is a clickable link to its
cached file.

Each item reads as its rule, its state, the finding, the recommended action and the sources. The checklist prepares
evidence for the analyst and credit officer; it never approves or declines credit (`checklist --help` says so too).
`--save-responses` saves a real model's responses: `--model anthropic` over the hand-written ones, `--model claude-code`
into `live-responses/`. Every run appends a line to
`audit/audit.jsonl`. The provider and model are set in `config.toml`. The production path is in
[`docs/production-note.md`](docs/production-note.md); the COO update and harvest bullets are in
[`docs/client-update.md`](docs/client-update.md).

| Folder | What it is |
|---|---|
| `checklist/criteria.py` | The versioned lending criteria and their deterministic checks |
| `checklist/engine.py` | A run: pull, offer uploads, then extract, decide, annotate, report, audit |
| `checklist/connectors.py` | The source connectors (CRM, SharePoint, broker email, all mocked) that fill the cache |
| `checklist/cache.py` | The local cache and the mocked document API over it: put, read this run's, prune, upload |
| `checklist/model.py` | The one model wrapper: anthropic, claude-code, replay or none |
| `sharepoint/` | The mocked SharePoint: generated PDFs, their origin and mocked extraction records |
| `scripts/make_documents.py` | Renders the stored documents as PDFs from their extraction records |
| `prompts/` | The two prompts the model gets |
| `applications/` | The two mocked applications, their saved model responses and expected reports |

## Use of AI

- **Tools and models.** Claude, by voice, as a thinking partner: reading the brief, the discovery questions,
  rehearsing the changed-facts scenarios and reviewing these documents. Voice was used heavily throughout. Storytree's
  session manager and coding agents (Claude Opus 5.5) for the repository, the planning, the build and these documents.
  In the prototype, Claude Opus 5.5 (set in `config.toml`) through the Anthropic SDK or Claude Code (`claude -p`),
  for extraction and annotation only.
- **Delegated.** The code, tests, synthetic data and first drafts of the documents. Mick made the design calls and
  reviewed the code and the documents.
- **Rejected or corrected.** The AI proposed a model-assisted check for fuzzy contradictions. Mick re-steered it:
  fixed functions make every call, and the model only annotates an item that has already failed, with a finding, a
  recommended action and its sources (it can raise a concern, never clear one). He also replaced the AI's state names
  (clear / needs attention / couldn't check) with lending terms: satisfied / exception / unable to verify.
- **Verified.** Mick ran the commands himself, read the output on the synthetic applications and gave feedback by
  voice; the agents reworked the build from it. The executable tests (`pytest`) check each planted issue and failure
  case.
