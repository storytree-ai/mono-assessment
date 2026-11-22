"""checklist [application id] [--details] [--model anthropic|replay|none] [--simulate-outage sharepoint] [--as-of YYYY-MM-DD]"""
import argparse
import json
import os
import sys
import tomllib
from datetime import date
from pathlib import Path

from .engine import SOURCES, run
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


def main(argv=None):
    config = tomllib.loads((ROOT / "config.toml").read_text())
    parser = argparse.ArgumentParser(
        prog="checklist", description="List the pending applications, or print one's current-state checklist. "
        "It prepares evidence for the analyst and credit officer; it never approves or declines credit.")
    parser.add_argument("application", nargs="?", help="an application id, for example app-1001")
    parser.add_argument("--details", action="store_true", help="also show the run id, model, criterion versions and documents")
    parser.add_argument("--model", choices=["anthropic", "replay", "none"], default=config["model"]["provider"],
                        help="where model calls go: a real call, the saved responses, or no model")
    parser.add_argument("--simulate-outage", action="append", choices=list(SOURCES), default=[],
                        help="treat a source system as unavailable")
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today(), metavar="YYYY-MM-DD", help="the date the checks run as of")
    parser.add_argument("--save-responses", action="store_true", help="with --model anthropic, save the responses for replay")
    args = parser.parse_args(argv)
    if args.application is None:
        print(list_pending())
        return
    folder = find(args.application)
    if folder is None:
        sys.exit(f"No application {args.application}; run checklist with no id to list the pending ones.")
    model = make_model(args.model, config["model"]["name"], folder, args.save_responses)
    report = run(folder, model, args.as_of, set(args.simulate_outage), ROOT / config["audit"]["path"])
    print(render(report, args.details, sys.stdout.isatty() and "NO_COLOR" not in os.environ))


if __name__ == "__main__":
    main()
