"""The source connectors: each pulls one source system's documents or records for an application into the cache.

All three are mocked by local folders of generated files; a real connector would call SharePoint, the CRM or the
mail system. A source being down stops its own connector's pull and nothing else.
"""
import json
from pathlib import Path

from . import cache

SHAREPOINT = Path(__file__).resolve().parent.parent / "sharepoint"
SOURCES = {"crm": "CRM", "sharepoint": "SharePoint", "email": "broker email"}


def files(folder: Path, into: Path, run_id: str, source: str) -> None:
    """The mocked CRM and mail system: the application's crm/ and email/ folders."""
    for file in sorted((folder / source).glob("*")):
        cache.put(into / source, file, {"file": file.name, "source": source, "origin": f"{SOURCES[source]} (mocked)"}, run_id)


def sharepoint(folder: Path, into: Path, run_id: str) -> None:
    """The mocked SharePoint: sharepoint/<application id>/, each document with its origin and extraction records."""
    for origin_file in sorted((SHAREPOINT / into.name).glob("*.origin.json")):
        origin = json.loads(origin_file.read_text())
        extraction = origin_file.with_name(origin_file.name.replace(".origin.json", ".extraction.json"))
        cache.put(into / cache.DOCUMENTS, origin_file.with_name(origin["file"]), {**origin, "source": "sharepoint"},
                  run_id, extraction if extraction.exists() else None)


def pull(folder: Path, into: Path, run_id: str, down: set[str]) -> None:
    for source in SOURCES:
        if source in down:
            continue
        if source == "sharepoint":
            sharepoint(folder, into, run_id)
        else:
            files(folder, into, run_id, source)
