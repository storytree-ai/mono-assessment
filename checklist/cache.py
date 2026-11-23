"""The local cache, a folder standing in for a cloud bucket: the connectors fill it and the checklist reads only it.

Each cached file sits beside <stem>.origin.json, naming where it came from and the run that put it there; a document
also sits beside <stem>.extraction.json, what was read from it. That extraction record is the seam where a real
document parser (for example Azure Document Intelligence or Amazon Textract) would write; here the records come
from the mocked SharePoint, so nothing in the checklist parses a PDF. A run reads only what it cached itself:
anything from another run is stale and treated as not there.
"""
import getpass
import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

CACHE = Path(__file__).resolve().parent.parent / "cache"
DOCUMENTS = "documents"
AWAITING = "document parser unavailable"


@dataclass
class Document:
    path: str
    source: str
    status: str
    text: str = ""
    file: str = ""
    error: str = ""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def put(folder: Path, file: Path, origin: dict, run_id: str, extraction: Path | None = None) -> None:
    """Caches one file under its origin["file"] name, stamped with the run that put it there."""
    folder.mkdir(parents=True, exist_ok=True)
    stem = Path(origin["file"]).stem
    shutil.copyfile(file, folder / origin["file"])
    if extraction:
        shutil.copyfile(extraction, folder / f"{stem}.extraction.json")
    (folder / f"{stem}.origin.json").write_text(json.dumps({**origin, "run_id": run_id, "cached_at": now()}, indent=2) + "\n")


def held(application: Path) -> list[dict]:
    """Everything the cache holds for one application, from any run: each file's path, origin and extraction."""
    entries = []
    for origin_file in sorted(application.glob("*/*.origin.json")):
        origin = json.loads(origin_file.read_text())
        extraction_file = origin_file.with_name(origin_file.name.replace(".origin.json", ".extraction.json"))
        extraction = json.loads(extraction_file.read_text()) if extraction_file.exists() else None
        sub = origin_file.parent.name
        entries.append({"path": origin["file"] if sub == DOCUMENTS else f"{sub}/{origin['file']}",
                        "file": origin_file.parent / origin["file"], "origin": origin, "extraction": extraction})
    return entries


def read(application: Path, run_id: str, sources: dict[str, str]) -> list[Document]:
    """This run's cached documents and records, through the mocked document API."""
    docs = []
    for entry in held(application):
        if entry["origin"]["run_id"] != run_id:
            continue
        source, file = sources.get(entry["origin"]["source"], "analyst upload"), entry["file"]
        if file.parent.name == DOCUMENTS:
            extraction = entry["extraction"] or {"status": AWAITING}
            status = {"done": "read", "failed": "unreadable"}.get(extraction["status"], AWAITING)
            docs.append(Document(entry["path"], source, status, extraction.get("text", ""), str(file),
                                 extraction.get("error", "")))
            continue
        try:
            text = file.read_text(encoding="utf-8")
            if file.suffix == ".json":
                json.loads(text)
            docs.append(Document(entry["path"], source, "read", text, str(file)))
        except ValueError:
            docs.append(Document(entry["path"], source, "unreadable", file=str(file)))
    return docs


def prune(cache: Path, days: int) -> None:
    """Drops every cache entry older than the retention period."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    for origin_file in cache.glob("*/*/*.origin.json"):
        origin = json.loads(origin_file.read_text())
        if datetime.fromisoformat(origin["cached_at"]) < cutoff:
            stem = origin_file.name.removesuffix(".origin.json")
            for gone in (origin_file.with_name(origin["file"]), origin_file.with_name(f"{stem}.extraction.json"), origin_file):
                gone.unlink(missing_ok=True)


def upload(application: Path, file: Path, kind: str, note: str, run_id: str) -> str:
    """An analyst's upload, inside a run: named for its kind, recording where it came from."""
    taken = {Path(e["path"]).stem for e in held(application)}
    doc_id, n = kind, 1
    while doc_id in taken:
        n += 1
        doc_id = f"{kind}-{n}"
    name = f"{doc_id}{file.suffix.lower()}"
    put(application / DOCUMENTS, file, {"file": name, "kind": kind, "source": "upload", "origin": "uploaded by hand",
                                        "uploaded_by": getpass.getuser(), "uploaded_from": str(file.resolve()),
                                        "note": note}, run_id)
    return name
