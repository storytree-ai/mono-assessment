"""Writes each extracted document in the mocked SharePoint as a one-page PDF of its text (GENERATED synthetic documents).

The extraction records are the source of truth for the mocked documents; this script renders them as real files
so an analyst can open them. It needs no library: the PDF is written by hand.
"""
import json
from pathlib import Path

STORE = Path(__file__).resolve().parent.parent / "sharepoint"


def pdf(lines: list[str]) -> bytes:
    escape = lambda line: line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    text = "BT /F1 11 Tf 15 TL 56 790 Td " + " ".join(f"({escape(line)}) '" for line in lines) + " ET"
    objects = ["<< /Type /Catalog /Pages 2 0 R >>", "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
               "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> "
               "/Contents 5 0 R >>",
               "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
               f"<< /Length {len(text.encode('cp1252'))} >>\nstream\n{text}\nendstream"]
    out = b"%PDF-1.4\n% GENERATED synthetic document, build agent 2026-11-22\n"
    offsets = []
    for number, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n{body}\nendobj\n".encode("cp1252")
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{offset:010} 00000 n \n".encode() for offset in offsets)
    return out + f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()


if __name__ == "__main__":
    for record in sorted(STORE.glob("*/*.extraction.json")):
        extraction = json.loads(record.read_text())
        if extraction["status"] == "done":
            (record.parent / extraction["document"]).write_bytes(pdf(extraction["text"].splitlines()))
            print("wrote", record.parent / extraction["document"])
