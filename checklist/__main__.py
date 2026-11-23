"""checklist [application id] [--details] [--model anthropic|claude-code|replay|none] [--simulate-outage sharepoint] [--as-of YYYY-MM-DD]
checklist documents <application id>"""
import argparse
import json
import os
import sys
import tomllib
from datetime import date
from pathlib import Path

from . import cache
from .connectors import SOURCES
from .criteria import CRITERIA
from .engine import cache_folder, run
from .model import make_model
from .report import render

ROOT = Path(__file__).resolve().parent.parent
APPLICATIONS = ROOT / "applications"


def pending(applications: Path = APPLICATIONS) -> list[dict]:
    """Every application in the mocked CRM is one flagged for manual review."""
    return [json.loads(record.read_text()) for record in sorted(applications.glob("*/crm/record.json"))]


def find(application_id: str, applications: Path = APPLICATIONS) -> Path | None:
    wanted = application_id.lower()
    return next((f for f in sorted(applications.iterdir()) if f.name == wanted or f.name.startswith(wanted + "-")), None)


def list_pending() -> str:
    lines = [f"{'Application':<12} {'Applicant':<28} {'Loan':>9}  Asset"]
    lines += [f"{r['application_id']:<12} {r['applicant']:<28} {'$' + format(r['loan_amount'], ','):>9}  {r['asset']}"
              for r in pending()]
    return "\n".join(["Pending applications", ""] + lines + ["", "Open one with: checklist <application id>"])


def application(application_id: str) -> Path:
    folder = find(application_id)
    if folder is None:
        sys.exit(f"No application {application_id}; run checklist with no id to list the pending ones.")
    return folder


def list_documents(folder: Path, cache_root: Path) -> str:
    held = cache_folder(cache_root, folder)
    status = {"done": "parsed", "failed": "parser failed"}
    lines = []
    for e in cache.held(held):
        state = "record" if "/" in e["path"] else status.get((e["extraction"] or {}).get("status"), cache.AWAITING)
        origin = e["origin"]
        lines.append(f"  {e['path']:<28} {state:<20} " + ", ".join(filter(None, (
            f"run {origin['run_id']}", origin["origin"], origin.get("uploaded_by"), origin["cached_at"], origin.get("note")))))
    return "\n".join([f"What the cache holds for {held.name}, from every run", ""] + (lines or ["  none"]))


KINDS = [c.document for c in CRITERIA if c.document]


def offer_upload(docs: list) -> list[tuple]:
    """After the run's pull: shows what it fetched and asks for any more documents, until Enter on its own."""
    print("This run fetched: " + (", ".join(d.path for d in docs) or "nothing"))
    uploads = []
    while answer := input("Upload a document (its file path, or Enter to run the checklist): ").strip():
        file = Path(answer).expanduser()
        kind = input(f"What is it? ({', '.join(KINDS)}): ").strip()
        if not file.is_file() or kind not in KINDS:
            print(f"Not uploaded: {'no file ' + str(file) if not file.is_file() else 'kind must be one of the above'}.")
            continue
        uploads.append((file, kind, input("Where did it come from? ").strip()))
    print()
    return uploads


SYSTEM_ERROR = "The checklist could not be built: a system error, not a finding about this application."


def main(argv=None):
    """The top-level classifier: an error no lower layer turned into a status is a plain system error, never a
    traceback; the raw error shows only under --details."""
    argv = sys.argv[1:] if argv is None else argv
    try:
        checklist(argv)
    except Exception as error:
        print(SYSTEM_ERROR + (f"\n{type(error).__name__}: {error}" if "--details" in argv else ""), file=sys.stderr)
        sys.exit(1)


def checklist(argv: list[str]):
    config = tomllib.loads((ROOT / "config.toml").read_text())
    cache_root = ROOT / config["cache"]["path"]
    if argv[:1] == ["documents"]:
        if len(argv) != 2:
            sys.exit("usage: checklist documents <application id>")
        return print(list_documents(application(argv[1]), cache_root))
    parser = argparse.ArgumentParser(
        prog="checklist", description="List the pending applications, or print one's current-state checklist. "
        "It prepares evidence for the analyst and credit officer; it never approves or declines credit.")
    parser.add_argument("application", nargs="?", help="an application id, for example app-1001")
    parser.add_argument("--details", action="store_true", help="also show the run id, model, criterion versions and documents")
    parser.add_argument("--model", choices=["anthropic", "claude-code", "replay", "none"], default=config["model"]["provider"],
                        help="where model calls go: a real call (API key or Claude Code), the saved responses, or no model")
    parser.add_argument("--simulate-outage", action="append", choices=list(SOURCES), default=[],
                        help="treat a source system as unavailable")
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today(), metavar="YYYY-MM-DD", help="the date the checks run as of")
    parser.add_argument("--save-responses", action="store_true", help="with a real model, save its responses")
    args = parser.parse_args(argv)
    if args.application is None:
        print(list_pending())
        return
    folder = application(args.application)
    model = make_model(args.model, config["model"]["name"], folder, args.save_responses)
    report = run(folder, model, args.as_of, set(args.simulate_outage), ROOT / config["audit"]["path"], cache_root,
                 config["cache"]["retention_days"], offer_upload if sys.stdin.isatty() else None)
    print(render(report, args.details, sys.stdout.isatty() and "NO_COLOR" not in os.environ))


if __name__ == "__main__":
    main()
