"""Runs one application through the checklist: load, extract, decide, annotate, report, audit."""
import json
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

from . import documents
from .criteria import EXCEPTION, EXTRACTED_INPUTS, SATISFIED, UNABLE, Criterion, applicable
from .documents import AWAITING, Document

PROMPTS = Path(__file__).resolve().parent.parent / "prompts"
SOURCES = {"crm": "CRM", "sharepoint": "SharePoint", "email": "broker email"}
DOCUMENT_SOURCE = "sharepoint"


def store_folder(store: Path, folder: Path) -> Path:
    """An application's place in the document store, by its id: app-1001-excavator keeps its documents in APP-1001."""
    return store / "-".join(folder.name.split("-")[:2]).upper()


def load_documents(folder: Path, down: set[str], store: Path) -> list[Document]:
    docs = []
    for top, source in SOURCES.items():
        if top in down:
            continue
        if top == DOCUMENT_SOURCE:
            docs += documents.read(store_folder(store, folder), source)
            continue
        for file in sorted((folder / top).glob("*")):
            path = f"{top}/{file.name}"
            try:
                text = file.read_text(encoding="utf-8")
                if file.suffix == ".json":
                    json.loads(text)
                docs.append(Document(path, source, "read", text, str(file)))
            except ValueError:
                docs.append(Document(path, source, "unreadable", file=str(file)))
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
})
ANNOTATE_SCHEMA = obj({"annotations": items_of({
    **{k: TEXT for k in ("criterion", "finding", "recommended_action", "chase_by", "concern")},
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


HAND_CHECK = {
    "source unavailable": "Check the documents in SharePoint by hand, or rerun once it is back.",
    "unreadable": "Open the file and check it by hand, or ask for a fresh copy.",
    AWAITING: "Open the file and check it by hand, or rerun once it has been extracted.",
    "model unavailable": "Open the documents below and check them by hand.",
    "please check": "Check the document by hand.",
}


def gate(c: Criterion, found: list[Document], down: set[str]):
    """The states an item takes before its check can run at all."""
    if DOCUMENT_SOURCE in down:
        return UNABLE, "source unavailable", "SharePoint is unavailable."
    if not found:
        return EXCEPTION, "missing", f"No {c.document.replace('-', ' ')} on file."
    unreadable = [Path(d.path).name for d in found if d.status == "unreadable"]
    if unreadable:
        return UNABLE, "unreadable", f"{', '.join(unreadable)} can't be read."
    waiting = [d.path for d in found if d.status == AWAITING]
    if waiting:
        return UNABLE, AWAITING, f"{', '.join(waiting)}: awaiting extraction."
    return None


def decide(c: Criterion, docs: list[Document], extraction: dict, as_of: date, down: set[str]) -> dict:
    found = [d for d in docs if c.document and Path(d.path).name.startswith(c.document)]
    item = {"criterion": c.key, "title": c.title, "applies_when": c.applies_when,
            "documents": [d.path for d in found], "sources": [], "annotation": None, "concern": None}
    inputs = {}
    for name, (path, key) in c.structured.items():
        inputs[name] = structured(docs, path).get(key)
        item["sources"].append({"ref": f"{path}#{key}", "field": key, "value": inputs[name]})
    result = gate(c, found, down) if c.document else None
    if result is None and c.extracted and extraction is None:
        result = UNABLE, "model unavailable", ""
    for name in c.extracted if result is None else ():
        got = [i for i in extraction["inputs"] if i["criterion"] == c.key and i["name"] == name]
        item["sources"] += [{"ref": i["source"], "quote": i["quote"]} for i in got]
        inputs[name] = [i["value"] for i in got]
        if not got or not all(inputs[name]):
            result = UNABLE, "please check", f"The model couldn't read the {name.replace('_', ' ')} clearly."
            break
    if result is None:
        try:
            result = c.check(inputs, as_of)
        except ValueError:
            result = UNABLE, "please check", f"An extracted value isn't in the expected form: {inputs}"
    state, reason, finding = result
    item.update(state=state, reason=reason, finding=finding, action=HAND_CHECK.get(reason, ""),
                function={"state": state, "reason": reason, "finding": finding})
    return item


def annotate(model, docs: list[Document], items: list[dict]) -> None:
    shown = [{k: item[k] for k in ("criterion", "title", "state", "reason", "finding", "sources")}
             for item in items]
    system = (PROMPTS / "annotate.md").read_text()
    answer = model.ask("annotate", system, as_prompt(docs, "Checklist items", shown), ANNOTATE_SCHEMA)
    by_key = {item["criterion"]: item for item in items}
    for note in answer["annotations"]:
        item = by_key.get(note["criterion"])
        if item is None or item["reason"] == AWAITING:
            continue
        if note["finding"] or note["recommended_action"]:
            item["annotation"] = {k: note[k] for k in ("finding", "recommended_action", "chase_by")}
        if note["concern"]:
            item["concern"] = {"text": note["concern"], "sources": note["concern_sources"]}
            if item["function"]["state"] == SATISFIED:
                item["state"], item["reason"] = EXCEPTION, "model concern"


def run(folder: Path, model, as_of: date, down: set[str] = frozenset(), audit: Path | None = None,
        store: Path = documents.STORE) -> dict:
    docs = load_documents(folder, down, store)
    record = structured(docs, "crm/record.json")
    criteria = applicable(record) if record else []
    items, note = [], None
    if criteria:
        try:
            extraction = extract(model, docs, criteria)
        except Exception as failure:
            extraction, note = None, f"unavailable ({failure})"
        items = [decide(c, docs, extraction, as_of, down) for c in criteria]
        if extraction:
            try:
                annotate(model, docs, items)
            except Exception as failure:
                note = f"annotations unavailable ({failure})"
    report = {
        "run_id": uuid.uuid4().hex[:12],
        "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "as_of": as_of.isoformat(),
        "folder": str(folder),
        "application": record,
        "model": {"provider": model.provider, "name": model.name, "note": note},
        "sources": {name: "unavailable" if top in down else "up" for top, name in SOURCES.items()},
        "documents": [{"path": d.path, "source": d.source, "status": d.status, "file": d.file} for d in docs],
        "criteria": [c.key for c in criteria],
        "items": items,
        "summary": {s: sum(i["state"] == s for i in items) for s in (SATISFIED, EXCEPTION, UNABLE)},
    }
    if audit:
        audit.parent.mkdir(parents=True, exist_ok=True)
        with audit.open("a") as log:
            log.write(json.dumps(report) + "\n")
    return report
