# Client update and harvest

## Update for HarbourLine's COO

The first working version of the evidence checklist is ready to show your analysts. On two made-up test applications,
it caught every missing, expired and contradictory item we planted, and pointed to the document behind each one. When
a document could not be read, it said so and left it to the analyst rather than guessing. It never approves or
declines a loan, and it changes nothing in your systems.

It has not yet been measured on real cases, and its security has not been reviewed, so it is not ready for live use.

The main risk is trust: after two earlier pilots made extra work, analysts will only adopt a tool that clearly saves
them time.

The decision we need from you: who in privacy will agree how past cases can be used to measure it, and which
analysts join the pilot.

## What to harvest into a reusable monō pattern

- **A versioned library of fixed checks.** Each evidence rule is a small named, versioned check saying when it
  applies and what it reads; the engine runs any list of them, so the next lender writes rules, not a tool.
- **The model can raise a flag, never clear one.** A model concern turns a passed item into an exception but cannot
  pass a failed one, and the rule's own result is kept beside it.
- **"Can't check" is never "missing".** When the model, a source or a file is unavailable, the item reads "unable to
  verify" with its documents and a by-hand step, so an outage never triggers a needless chase.
