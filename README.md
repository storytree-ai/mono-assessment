# Mono assessment

Mick's take-home assessment for Mono, an AI startup.

**Status: first slice built on branch build/first-slice, for Mick's review.** The plan lives in the storytree project `mono-assessment`.

## Approach (from Mick, 2026-11-21)

- An AI-compiled audit checklist: an agent pulls the relevant documents together, assesses each against the
  assessment criteria, and outputs conclusions about the candidate. Each conclusion carries a source link back to its
  document.
- Deterministic checks against the criteria where possible. The model adds a one-sentence comment under an item where
  it finds something odd, quotes its source, and flags contradictions.
- First slice: mocked documents, all in one place, as a prototype that shows evidence. A full version would pull from
  SharePoint and the CRM.

The assessment brief (PDF) goes in [`brief/`](brief/).

## Run it (first slice, branch build/first-slice)

Python 3.12. Everything under `applications/` is generated synthetic data.

```sh
python3 -m venv .venv            # on a box without ensurepip: python3 -m venv --without-pip .venv, then get-pip.py
.venv/bin/python -m pip install pytest anthropic
.venv/bin/python -m pytest       # six tests; no model is called, no API key needed

.venv/bin/python -m checklist applications/app-1001-excavator --as-of 2026-11-22     # replays the saved model responses
.venv/bin/python -m checklist applications/app-1002-tipper --as-of 2026-11-22
.venv/bin/python -m checklist applications/app-1001-excavator --model none           # the no-model mode
.venv/bin/python -m checklist applications/app-1001-excavator --down sharepoint      # a source system down
.venv/bin/python -m checklist applications/app-1001-excavator --model anthropic      # a real call (ANTHROPIC_API_KEY)
```

`--record` with `--model anthropic` saves the real responses over the hand-written ones. Every run appends a line to
`audit/audit.jsonl`. The provider and model are set in `config.toml`. Next steps are in
[`docs/production-note.md`](docs/production-note.md).

| Folder | What it is |
|---|---|
| `checklist/criteria.py` | The versioned lending criteria and their deterministic checks |
| `checklist/engine.py` | Load, extract, decide, annotate, report, audit |
| `checklist/model.py` | The one model wrapper: anthropic, replay or none |
| `prompts/` | The two prompts the model gets |
| `applications/` | The two mocked applications, their saved model responses and expected reports |
