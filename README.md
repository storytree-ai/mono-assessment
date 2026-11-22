# Mono assessment

Mick's take-home assessment for Mono, an AI startup.

**Status: first slice built, with the fixes from Mick's review of it, for his review.** The plan lives in the storytree project `mono-assessment`.

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

Python 3.12. Everything under `applications/` is generated synthetic data.

```sh
python3 -m venv .venv            # on a box without ensurepip: python3 -m venv --without-pip .venv, then get-pip.py
.venv/bin/python -m pip install -e . pytest     # installs the checklist command into .venv
.venv/bin/python -m pytest       # no model is called, no API key needed
source .venv/bin/activate        # then checklist is one word

checklist                                                     # the pending applications
checklist app-1001 --as-of 2026-11-22                         # one application; replays the saved model responses
checklist app-1002 --as-of 2026-11-22
checklist app-1001 --model none                               # the no-model mode
checklist app-1001 --simulate-outage sharepoint               # a source system down
checklist app-1001 --model anthropic                          # a real call (ANTHROPIC_API_KEY)
```

`--save-responses` with `--model anthropic` saves the real responses over the hand-written ones. Every run appends a line to
`audit/audit.jsonl`. The provider and model are set in `config.toml`. Next steps are in
[`docs/production-note.md`](docs/production-note.md).

| Folder | What it is |
|---|---|
| `checklist/criteria.py` | The versioned lending criteria and their deterministic checks |
| `checklist/engine.py` | Load, extract, decide, annotate, report, audit |
| `checklist/model.py` | The one model wrapper: anthropic, replay or none |
| `prompts/` | The two prompts the model gets |
| `applications/` | The two mocked applications, their saved model responses and expected reports |
