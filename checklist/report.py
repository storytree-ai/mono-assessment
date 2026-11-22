"""The analyst-facing exception brief, as plain text."""
from pathlib import Path


def link(report: dict, path: str) -> str:
    return str(Path(report["folder"]) / path.split("#")[0]) + ("#" + path.split("#")[1] if "#" in path else "")


def source_line(report: dict, source: dict) -> str:
    said = f'"{source["quote"]}"' if "quote" in source else f"= {source['value']}"
    return f"    - {link(report, source['ref'])}  {said}"


def render(report: dict) -> str:
    app, s = report["application"], report["summary"]
    lines = ["HarbourLine Finance: exception brief (prototype, GENERATED synthetic data)",
             "For the analyst and credit officer. This tool does not approve or decline credit."]
    if app:
        lines.append(f"{app['application_id']}  {app['applicant']}  ${app['loan_amount']:,}  {app['asset']}")
    else:
        lines.append("The CRM record is unavailable, so no checklist can be built; the documents found are listed below.")
    model = report["model"]
    lines += [f"Run {report['run_id']} at {report['run_at']} (as of {report['as_of']}); "
              f"model {model['name']} ({model['provider']})" + (f": {model['note']}" if model.get("note") else ""),
              f"{s['satisfied']} satisfied, {s['exception']} exception, {s['unable to verify']} unable to verify", ""]
    for item in report["items"]:
        head = item["state"].upper() + (f" ({item['reason']})" if item["reason"] else "")
        lines.append(f"[{head}] {item['title']}  ({item['criterion']}, applies to {item['applies_when']})")
        lines.append(f"  Rule: {item['detail']}")
        if item["annotation"]:
            lines.append(f"  What happened: {item['annotation']['what_happened']}")
            lines.append(f"  Next step: {item['annotation']['call_to_action']}")
        if item["concern"]:
            lines.append(f"  Model concern: {item['concern']['text']} "
                         f"(sources: {', '.join(item['concern']['sources'])})")
        if item["promise"]:
            p = item["promise"]
            due = f", expected by {p['expected_by']}" if p["expected_by"] else ""
            lines.append(f"  Promised: {p['text']}{due}  ({link(report, p['source'])}: \"{p['quote']}\")")
        lines.append("  Sources:")
        refs = [source_line(report, src) for src in item["sources"]]
        refs += [f"    - {link(report, d)}" for d in item["documents"] if all(s["ref"] != d for s in item["sources"])]
        lines += refs or ["    - none found"]
        lines.append("")
    lines.append("Sources: " + ", ".join(f"{name} {state}" for name, state in report["sources"].items()))
    lines.append("Documents:")
    lines += [f"  - {link(report, d['path'])}  ({d['source']}, {d['status']})" for d in report["documents"]]
    return "\n".join(lines)
