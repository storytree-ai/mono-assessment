# Client update and harvest (first draft)

Status: a minimal first draft of Deliverable 4, for Mick to add to.

## Update for HarbourLine's COO

What we built: a first working version, on made-up data, that reads a flagged loan application and lists what is
missing, out of date or does not match, showing where each finding came from. It never approves or declines a loan.
It is not yet connected to your systems.

What it means for the backlog: analysts start from a short list of problems instead of every document, which should
cut preparation time. The pilot will measure by how much.

The one risk worth knowing: To confirm with Mick (the brief points to analysts' trust after two earlier pilots made
extra work, and privacy approval for the model).

What we need from you next: a privacy or compliance contact to agree how customer data may be used, and time with a
few pilot analysts.

## What to harvest into a reusable monō pattern

- **The model reads, the rules decide.** The model pulls each value out of a document with a pointer to where it
  found it; fixed code applies the lending rules.
- **Versioned rules and a run record.** Each checklist item names the exact version of the rule it was checked
  against, and every run adds a record that is never edited.
- **A no-model mode.** If the model is down or not allowed, the fixed checks still run and the documents are listed
  with links, so work carries on.
