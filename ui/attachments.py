"""Decode chat uploads and turn them into Gemini parts plus prompt text."""

from __future__ import annotations

import base64
import zipfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree as ET

from fastapi import HTTPException

MAX_FILES = 5
MAX_BYTES = 8 * 1024 * 1024
INLINE_MIMES = {"application/pdf", "image/png", "image/jpeg", "image/webp"}
ALLOWED_SUFFIXES = {
    ".pdf": "application/pdf",
    ".csv": "text/csv",
    ".txt": "text/plain",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xls": "application/vnd.ms-excel",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".doc": "application/msword",
}


@dataclass(frozen=True)
class DecodedAttachment:
    filename: str
    mime_type: str
    data: bytes


def decode_attachments(raw: list[dict[str, str]]) -> list[DecodedAttachment]:
    if len(raw) > MAX_FILES:
        raise HTTPException(status_code=400, detail="Too many attachments")
    decoded: list[DecodedAttachment] = []
    for item in raw:
        name = Path(str(item.get("filename") or "upload")).name
        suffix = Path(name).suffix.lower()
        if suffix not in ALLOWED_SUFFIXES:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {name}",
            )
        try:
            data = base64.b64decode(item.get("content_base64") or "", validate=False)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Could not read {name}") from exc
        if not data:
            raise HTTPException(status_code=400, detail=f"{name} is empty")
        if len(data) > MAX_BYTES:
            raise HTTPException(status_code=400, detail=f"{name} is larger than 8 MB")
        mime = str(item.get("mime_type") or "").strip() or ALLOWED_SUFFIXES[suffix]
        decoded.append(DecodedAttachment(filename=name, mime_type=mime, data=data))
    return decoded


def prompt_and_inline(
    message: str, attachments: list[DecodedAttachment]
) -> tuple[str, list[DecodedAttachment]]:
    """Return the user text (with extracted sheets/docs) and files Gemini can take inline."""
    extra: list[str] = []
    inline: list[DecodedAttachment] = []
    for item in attachments:
        suffix = Path(item.filename).suffix.lower()
        if item.mime_type in INLINE_MIMES or suffix == ".pdf":
            inline.append(item)
            extra.append(f"Attached file: {item.filename}")
            continue
        extracted = _extract_text(item.filename, suffix, item.data)
        extra.append(f"Attached {item.filename}:\n{extracted}")
    if not extra:
        return message, inline
    return message.rstrip() + "\n\n" + "\n\n".join(extra), inline


def _extract_text(filename: str, suffix: str, data: bytes) -> str:
    if suffix in {".txt", ".csv"}:
        return data.decode("utf-8", errors="replace")[:20_000]
    if suffix == ".xlsx":
        return _xlsx_text(data) or f"(No readable cells in {filename}.)"
    if suffix == ".docx":
        return _docx_text(data) or f"(No readable text in {filename}.)"
    return (
        f"(Binary {filename} attached; contents are not parsed in this workspace. "
        "Summarize from the filename if needed.)"
    )


def _xlsx_text(data: bytes) -> str:
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    try:
        with zipfile.ZipFile(BytesIO(data)) as archive:
            shared: list[str] = []
            if "xl/sharedStrings.xml" in archive.namelist():
                root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
                for node in root.findall("m:si", ns):
                    shared.append(
                        "".join(
                            (part.text or "")
                            for part in node.iter(
                                "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t"
                            )
                        )
                    )
            lines: list[str] = []
            sheets = sorted(
                name
                for name in archive.namelist()
                if name.startswith("xl/worksheets/sheet") and name.endswith(".xml")
            )
            for sheet in sheets[:4]:
                root = ET.fromstring(archive.read(sheet))
                for row in root.findall("m:sheetData/m:row", ns):
                    cells: list[str] = []
                    for cell in row.findall("m:c", ns):
                        value = cell.find("m:v", ns)
                        if value is None or value.text is None:
                            cells.append("")
                            continue
                        if cell.get("t") == "s":
                            index = int(value.text)
                            cells.append(shared[index] if index < len(shared) else value.text)
                        else:
                            cells.append(value.text)
                    if any(cell.strip() for cell in cells):
                        lines.append(" | ".join(cells))
            return "\n".join(lines[:250])
    except Exception:
        return ""


def _docx_text(data: bytes) -> str:
    try:
        with zipfile.ZipFile(BytesIO(data)) as archive:
            root = ET.fromstring(archive.read("word/document.xml"))
        texts = [
            node.text
            for node in root.iter()
            if node.tag.endswith("}t") and node.text
        ]
        return "\n".join(texts)[:20_000]
    except Exception:
        return ""
