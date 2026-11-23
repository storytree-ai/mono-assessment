"""The analyst-facing exception brief, for the terminal."""
from datetime import date
from pathlib import Path

from .criteria import EXCEPTION, SATISFIED, UNABLE, day

STYLE = {"bold": "1", "dim": "2", SATISFIED: "32", EXCEPTION: "31", UNABLE: "33"}
LABELS = {"abn": "ABN", "loan_amount": "Loan amount", "report_date": "Report date"}
NAMES = {"crm/record.json": "CRM record", "crm/credit-report.json": "credit report"}
WIDTH = 20


class Brief:
    def __init__(self, colour: bool):
        self.colour, self.lines = colour, []

    def style(self, text: str, key: str) -> str:
        return f"\033[{STYLE[key]}m{text}\033[0m" if self.colour else text

    def link(self, text: str, file: str) -> str:
        """A clickable terminal hyperlink (OSC 8) to the stored file; terminals without them show the text."""
        return f"\033]8;;{Path(file).as_uri()}\033\\{text}\033]8;;\033\\" if self.colour and file else text

    def field(self, label: str, value: str, indent: str = "  "):
        self.lines.append(f"{indent}{label:<{WIDTH}}{value}")


def money(value) -> str:
    return f"${float(value):,.0f}"


def name(path: str) -> str:
    return NAMES.get(path, Path(path).name)


def linked(brief: Brief, report: dict, path: str) -> str:
    file = next((d["file"] for d in report["documents"] if d["path"] == path), "")
    return brief.link(name(path), file)


def source_text(brief: Brief, report: dict, source: dict) -> str:
    path = source["ref"].split("#")[0]
    if "quote" in source:
        return f'"{source["quote"]}" · {linked(brief, report, path)}'
    value = money(source["value"]) if source["field"] == "loan_amount" else source["value"]
    label = LABELS.get(source["field"], source["field"].replace("_", " ").capitalize())
    return f"{label}: {value} · {linked(brief, report, path)}"


def notices(report: dict) -> list[str]:
    said = []
    for source, state in report["sources"].items():
        if state == "unavailable":
            said.append(f"{source} is unavailable: items with nothing in this run's cache can't progress until it is back.")
    note = report["model"].get("note") or ""
    if note.startswith("unavailable"):
        said.append("The model is unavailable: the document items are left to you, with their documents linked.")
    elif note:
        said.append("The model's notes are unavailable: each item shows the rule's own finding.")
    return said


def item_lines(brief: Brief, report: dict, item: dict, details: bool):
    note = item["annotation"] or {}
    brief.lines.append(brief.style(item["title"], "bold"))
    brief.lines.append("  " + brief.style(item["state"].capitalize(), item["state"]))
    if note.get("finding") or item["finding"]:
        brief.field("Finding", note.get("finding") or item["finding"])
    if item["concern"]:
        brief.field("Concern", item["concern"]["text"] + " · " + ", ".join(linked(brief, report, p) for p in item["concern"]["sources"]))
    if note.get("recommended_action") or item["action"]:
        brief.field("Recommended action", note.get("recommended_action") or item["action"])
    if note.get("chase_by"):
        brief.field("", f"Chase by {day(date.fromisoformat(note['chase_by']))}")
    refs = [source_text(brief, report, s) for s in item["sources"]]
    refs += [linked(brief, report, d) for d in item["documents"] if all(s["ref"] != d for s in item["sources"])]
    for n, ref in enumerate(refs or ["none found"]):
        brief.field("Sources" if n == 0 else "", ref)
    if details:
        brief.field("Criterion", " · ".join(filter(None, (item["criterion"], item["reason"], f"applies to {item['applies_when']}"))))
    brief.lines.append("")


def render(report: dict, details: bool = False, colour: bool = False) -> str:
    app, s = report["application"], report["summary"]
    brief = Brief(colour)
    if app:
        brief.lines += [brief.style(f"{app['application_id']} · {app['applicant']}", "bold"),
                        f"{app['product'].capitalize()}, flagged for review on {day(date.fromisoformat(app['flagged_for_review']))}.", ""]
        brief.field("Loan", money(app["loan_amount"]))
        for label in ("asset", "director", "broker"):
            brief.field(label.capitalize(), app[label])
        brief.lines.append("")
    else:
        brief.lines += ["The CRM record is unavailable, so no checklist can be built.", ""]
    brief.lines += notices(report) + ([""] if notices(report) else [])
    if report["items"]:
        counts = [brief.style(f"{s[state]} {label}", state) for state, label in
                  ((EXCEPTION, "exception" if s[EXCEPTION] == 1 else "exceptions"), (UNABLE, "unable to verify"),
                   (SATISFIED, "satisfied"))]
        brief.lines += [" · ".join(counts), ""]
    for item in report["items"]:
        item_lines(brief, report, item, details)
    if details or not app:
        model = report["model"]
        brief.lines.append(brief.style("Details", "bold"))
        brief.field("Run", f"{report['run_id']} at {report['run_at']}, as of {report['as_of']}")
        brief.field("Model", f"{model['name']} ({model['provider']})" + (f": {model['note']}" if model.get("note") else ""))
        brief.field("Sources", ", ".join(f"{n} {state}" for n, state in report["sources"].items()))
        for n, d in enumerate(report["documents"]):
            brief.field("Documents" if n == 0 else "", f"{d['file'] or d['path']} ({d['source']}, {d['status']})")
        brief.lines.append("")
    brief.lines.append(brief.style("Synthetic data: HarbourLine Finance and its applicants are fictional.", "dim"))
    return "\n".join(brief.lines)
