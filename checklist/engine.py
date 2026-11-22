"""Runs one application through the checklist: load, extract, decide, annotate, report, audit."""
import json
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

from .criteria import EXCEPTION, EXTRACTED_INPUTS, SATISFIED, UNABLE, Criterion, applicable

PROMPTS = Path(__file__).resolve().parent.parent / "prompts"
SOURCES = {"crm": "CRM", "sharepoint": "SharePoint", "email": "broker email"}
DOCUMENT_SOURCE = "sharepoint"


@dataclass
class Document:
    path: str
    source: str
    status: str
    text: str = ""


def load_documents(folder: Path, down: set[str]) -> list[Document]:
    docs = []
    for top, source in SOURCES.items():
        if top in down:
            continue
        for file in sorted((folder / top).glob("*")):
            path = f"{top}/{file.name}"
            try:
                text = file.read_text(encoding="utf-8")
                if file.suffix == ".json":
                    json.loads(text)
                docs.append(Document(path, source, "read", text))
            except ValueError:
                docs.append(Document(path, source, "unreadable"))
    return docs


def structured(docs: list[Document], path: str) -> dict:
    return next((json.loads(d.text) for d in docs if d.path == path and d.status == "read"), {})


def obj(props: dict) -> dict:
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


def items_of(props: dict) -> dict:
    return {"type": "array", "items": obj(props)}


TEXT = {"type": "string"}
EXTRACT_SCHEMA = obj({
    "inputs": items_of({k: TEXT for k in ("criterion", "name", "value", "source", "quote")}),
    "promises": items_of({k: TEXT for k in ("criterion", "text", "expected_by", "source", "quote")}),
})
ANNOTATE_SCHEMA = obj({"annotations": items_of({
    **{k: TEXT for k in ("criterion", "what_happened", "call_to_action", "concern")},
    "concern_sources": {"type": "array", "items": TEXT},
})})


def as_prompt(docs: list[Document], heading: str, payload) -> str:
    shown = [d for d in docs if d.status == "read" and d.source != "CRM"]
    parts = [f'<document path="{d.path}" source="{d.source}">\n{d.text}\n</document>' for d in shown]
    return "\n\n".join(parts + [f"{heading}:\n{json.dumps(payload, indent=2)}"])


def extract(model, docs: list[Document], criteria: list[Criterion]) -> dict:
    wanted = [{"criterion": c.key, "name": name, "means": EXTRACTED_INPUTS[name]}
              for c in criteria for name in c.extracted]
    system = (PROMPTS / "extract.md").read_text()
    return model.ask("extract", system, as_prompt(docs, "Inputs to extract", wanted), EXTRACT_SCHEMA)


def gate(c: Criterion, found: list[Document], down: set[str]):
    """The states an item takes before its check can run at all."""
    if DOCUMENT_SOURCE in down:
        return UNABLE, "source unavailable", "SharePoint is unavailable; check by hand, or rerun once it is back"
    if not found:
        return EXCEPTION, "missing", f"no {c.document} document on file"
    unreadable = [d.path for d in found if d.status == "unreadable"]
    if unreadable:
        return UNABLE, "unreadable", f"couldn't read {', '.join(unreadable)}, check manually"
    return None


def decide(c: Criterion, docs: list[Document], extraction: dict, as_of: date, down: set[str]) -> dict:
    found = [d for d in docs if c.document and Path(d.path).name.startswith(c.document)]
    item = {"criterion": c.key, "title": c.title, "applies_when": c.applies_when,
            "documents": [d.path for d in found], "sources": [], "promise": None,
            "annotation": None, "concern": None}
    inputs = {}
    for name, (path, key) in c.structured.items():
        inputs[name] = structured(docs, path).get(key)
        item["sources"].append({"ref": f"{path}#{key}", "value": inputs[name]})
    result = gate(c, found, down) if c.document else None
    for name in c.extracted if result is None else ():
        got = [i for i in extraction["inputs"] if i["criterion"] == c.key and i["name"] == name]
        item["sources"] += [{"ref": i["source"], "quote": i["quote"]} for i in got]
        inputs[name] = [i["value"] for i in got]
        if not got or not all(inputs[name]):
            result = UNABLE, "please check", f"the model could not read {name} clearly; check the document by hand"
            break
    if result is None:
        try:
            result = c.check(inputs, as_of)
        except ValueError:
            result = UNABLE, "please check", f"an extracted value could not be read as expected: {inputs}"
    state, reason, detail = result
    item.update(state=state, reason=reason, detail=detail,
                function={"state": state, "reason": reason, "detail": detail})
    if reason == "missing":
        promise = next((p for p in extraction["promises"] if p["criterion"] == c.key), None)
        if promise:
            item["promise"] = {"text": promise["text"], "expected_by": promise["expected_by"] or None,
                               "source": promise["source"], "quote": promise["quote"]}
    return item


def annotate(model, docs: list[Document], items: list[dict]) -> None:
    shown = [{k: item[k] for k in ("criterion", "title", "state", "reason", "detail", "sources", "promise")}
             for item in items]
    system = (PROMPTS / "annotate.md").read_text()
    answer = model.ask("annotate", system, as_prompt(docs, "Checklist items", shown), ANNOTATE_SCHEMA)
    by_key = {item["criterion"]: item for item in items}
    for note in answer["annotations"]:
        item = by_key.get(note["criterion"])
        if item is None:
            continue
        if item["state"] != SATISFIED and note["what_happened"]:
            item["annotation"] = {"what_happened": note["what_happened"], "call_to_action": note["call_to_action"]}
        if note["concern"]:
            item["concern"] = {"text": note["concern"], "sources": note["concern_sources"]}
            if item["function"]["state"] == SATISFIED:
                item["state"], item["reason"] = EXCEPTION, "model concern"


def run(folder: Path, model, as_of: date, down: set[str] = frozenset(), audit: Path | None = None) -> dict:
    docs = load_documents(folder, down)
    record = structured(docs, "crm/record.json")
    criteria = applicable(record) if record else []
    items = []
    if criteria:
        extraction = extract(model, docs, criteria)
        items = [decide(c, docs, extraction, as_of, down) for c in criteria]
        annotate(model, docs, items)
    report = {
        "run_id": uuid.uuid4().hex[:12],
        "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "as_of": as_of.isoformat(),
        "folder": str(folder),
        "application": record,
        "model": {"provider": model.provider, "name": model.name},
        "sources": {name: "unavailable" if top in down else "up" for top, name in SOURCES.items()},
        "documents": [{"path": d.path, "source": d.source, "status": d.status} for d in docs],
        "criteria": [c.key for c in criteria],
        "items": items,
        "summary": {s: sum(i["state"] == s for i in items) for s in (SATISFIED, EXCEPTION, UNABLE)},
    }
    if audit:
        audit.parent.mkdir(parents=True, exist_ok=True)
        with audit.open("a") as log:
            log.write(json.dumps(report) + "\n")
    return report
