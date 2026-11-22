"""The mocked document API over the local document store, a folder standing in for a cloud bucket.

Each stored file <id>.<ext> sits beside <id>.origin.json (where it came from) and, once extracted,
<id>.extraction.json (what was read from it). This is the seam where a real extraction service (for example Azure
Document Intelligence or Amazon Textract) would write that record; here the records are generated with the
documents, so nothing in the checklist parses a PDF.
"""
import getpass
import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

STORE = Path(__file__).resolve().parent.parent / "document-store"
AWAITING = "awaiting extraction"


@dataclass
class Document:
    path: str
    source: str
    status: str
    text: str = ""
    file: str = ""


def stored(folder: Path) -> list[dict]:
    """What the store holds for one application: each document's file, origin and extraction status."""
    held = []
    for origin_file in sorted(folder.glob("*.origin.json")):
        origin = json.loads(origin_file.read_text())
        extraction_file = folder / origin_file.name.replace(".origin.json", ".extraction.json")
        extraction = json.loads(extraction_file.read_text()) if extraction_file.exists() else {"status": AWAITING}
        held.append({"file": origin["file"], "origin": origin, "extraction": extraction})
    return held


def read(folder: Path, source: str) -> list[Document]:
    docs = []
    for held in stored(folder):
        status = {"done": "read", "failed": "unreadable"}.get(held["extraction"]["status"], AWAITING)
        docs.append(Document(held["file"], source, status, held["extraction"].get("text", ""),
                             str(folder / held["file"])))
    return docs


def upload(folder: Path, file: Path, kind: str, note: str = "") -> str:
    """Puts a document into the store, named for its kind, and records where it came from."""
    folder.mkdir(parents=True, exist_ok=True)
    taken = {Path(h["file"]).stem for h in stored(folder)}
    doc_id, n = kind, 1
    while doc_id in taken:
        n += 1
        doc_id = f"{kind}-{n}"
    shutil.copyfile(file, folder / f"{doc_id}{file.suffix.lower()}")
    origin = {"file": f"{doc_id}{file.suffix.lower()}", "kind": kind, "origin": "uploaded by hand",
              "uploaded_by": getpass.getuser(), "uploaded_from": str(file.resolve()),
              "added_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "note": note}
    (folder / f"{doc_id}.origin.json").write_text(json.dumps(origin, indent=2) + "\n")
    return origin["file"]
