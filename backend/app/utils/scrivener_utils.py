from __future__ import annotations

import io
import re
import uuid
import zipfile
from xml.etree import ElementTree

from defusedxml.common import DefusedXmlException
from defusedxml.ElementTree import fromstring as safe_xml_fromstring
from fastapi import HTTPException

SCRIVENER_MAX_ARCHIVE_ENTRIES = 5000
SCRIVENER_MAX_PROJECT_BYTES = 5 * 1024 * 1024
SCRIVENER_MAX_DOCUMENT_BYTES = 16 * 1024 * 1024
SCRIVENER_MAX_UNCOMPRESSED_BYTES = 64 * 1024 * 1024


def _validated_scrivener_members(archive: zipfile.ZipFile) -> dict[str, zipfile.ZipInfo]:
    members = [member for member in archive.infolist() if not member.is_dir()]
    if len(members) > SCRIVENER_MAX_ARCHIVE_ENTRIES:
        raise HTTPException(413, "Scrivener archive contains too many files.")
    if any(member.flag_bits & 0x1 for member in members):
        raise HTTPException(400, "Encrypted Scrivener archives are not supported.")
    if sum(max(int(member.file_size), 0) for member in members) > SCRIVENER_MAX_UNCOMPRESSED_BYTES:
        raise HTTPException(413, "Scrivener archive expands beyond the allowed size.")

    normalized: dict[str, zipfile.ZipInfo] = {}
    for member in members:
        name = member.filename.replace("\\", "/")
        if name in normalized:
            raise HTTPException(400, "Scrivener archive contains duplicate file names.")
        normalized[name] = member

    project_members = [
        member for name, member in normalized.items() if name.lower().endswith(".scrivx")
    ]
    if not project_members:
        raise HTTPException(400, "Scrivener archive is missing its .scrivx project file.")
    if len(project_members) > 1:
        raise HTTPException(400, "Scrivener archive must contain exactly one project file.")
    if project_members[0].file_size > SCRIVENER_MAX_PROJECT_BYTES:
        raise HTTPException(413, "Scrivener project metadata is too large.")
    return normalized


def _rtf_to_text(raw: bytes) -> str:
    text = raw.decode("latin-1", errors="replace")
    text = re.sub(
        r"\\'([0-9a-fA-F]{2})",
        lambda match: bytes.fromhex(match.group(1)).decode("cp1252", errors="replace"),
        text,
    )
    text = re.sub(
        r"\\u(-?\d+)\??",
        lambda match: chr(int(match.group(1)) % 65536),
        text,
    )
    text = re.sub(r"\\par[d]?\b\s?", "\n", text)
    text = re.sub(r"\\tab\b\s?", "\t", text)
    text = re.sub(r"\\[a-zA-Z]+-?\d*\s?", "", text)
    text = text.replace(r"\{", "{").replace(r"\}", "}").replace(r"\\", "\\")
    cleaned = re.sub(r"[{}]", "", text).strip()
    return cleaned.encode("utf-16", errors="surrogatepass").decode("utf-16")


def _text_to_rtf(text: str) -> bytes:
    escaped = []
    for char in text:
        code = ord(char)
        if char in {"\\", "{", "}"}:
            escaped.append(f"\\{char}")
        elif char == "\n":
            escaped.append("\\par\n")
        elif 32 <= code <= 126:
            escaped.append(char)
        elif code <= 0xFFFF:
            signed = code if code < 32768 else code - 65536
            escaped.append(f"\\u{signed}?")
        else:
            value = code - 0x10000
            high = 0xD800 + (value >> 10)
            low = 0xDC00 + (value & 0x3FF)
            escaped.extend((f"\\u{high - 65536}?", f"\\u{low - 65536}?"))
    return ("{\\rtf1\\ansi\\deff0\n" + "".join(escaped) + "\n}").encode("ascii")


def parse_scrivener_archive(raw: bytes) -> list[dict]:
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            members = _validated_scrivener_members(archive)
            project_member = next(
                member for name, member in members.items() if name.lower().endswith(".scrivx")
            )
            root = safe_xml_fromstring(archive.read(project_member))
            draft = next(
                (
                    item
                    for item in root.iter("BinderItem")
                    if str(item.attrib.get("Type") or "").lower() == "draftfolder"
                ),
                None,
            )
            candidates = (
                list(draft.iter("BinderItem"))
                if draft is not None
                else list(root.iter("BinderItem"))
            )
            chapters = []
            for item in candidates:
                if str(item.attrib.get("Type") or "").lower() != "text":
                    continue
                item_id = str(item.attrib.get("UUID") or item.attrib.get("ID") or "").strip()
                if not item_id:
                    continue
                title_node = item.find("Title")
                title = str(title_node.text if title_node is not None else "").strip() or "Untitled"
                suffixes = (
                    f"Files/Data/{item_id}/content.rtf",
                    f"Files/Data/{item_id}/content.txt",
                )
                content_name = next((name for name in members if name.endswith(suffixes)), None)
                if content_name is None:
                    continue
                content_member = members[content_name]
                if content_member.file_size > SCRIVENER_MAX_DOCUMENT_BYTES:
                    raise HTTPException(413, "A Scrivener manuscript document is too large.")
                content = archive.read(content_member)
                text = (
                    _rtf_to_text(content)
                    if content_name.lower().endswith(".rtf")
                    else content.decode("utf-8", errors="replace")
                )
                if text.strip():
                    chapters.append({"number": len(chapters) + 1, "title": title, "text": text})
            if not chapters:
                raise HTTPException(
                    400, "No manuscript documents were found in this Scrivener project."
                )
            return chapters
    except zipfile.BadZipFile as exc:
        raise HTTPException(400, "Invalid Scrivener archive.") from exc
    except (ElementTree.ParseError, DefusedXmlException) as exc:
        raise HTTPException(400, "Scrivener project metadata is invalid.") from exc


def build_scrivener_archive(project_title: str, chapters: list[dict]) -> bytes:
    safe_stem = re.sub(r"[^A-Za-z0-9_-]+", "-", project_title).strip("-") or "LoreVia-Project"
    project_folder = f"{safe_stem}.scriv"
    root = ElementTree.Element(
        "ScrivenerProject", Version="2.0", Identifier=str(uuid.uuid4()).upper()
    )
    binder = ElementTree.SubElement(root, "Binder")
    draft = ElementTree.SubElement(
        binder, "BinderItem", UUID=str(uuid.uuid4()).upper(), Type="DraftFolder"
    )
    ElementTree.SubElement(draft, "Title").text = "Manuscript"
    children = ElementTree.SubElement(draft, "Children")
    documents = []
    for chapter in chapters:
        item_id = str(uuid.uuid4()).upper()
        item = ElementTree.SubElement(children, "BinderItem", UUID=item_id, Type="Text")
        ElementTree.SubElement(item, "Title").text = str(chapter.get("title") or "Untitled")
        documents.append((item_id, str(chapter.get("text") or "")))
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            f"{project_folder}/{safe_stem}.scrivx",
            ElementTree.tostring(root, encoding="utf-8", xml_declaration=True),
        )
        for item_id, text in documents:
            archive.writestr(
                f"{project_folder}/Files/Data/{item_id}/content.rtf",
                _text_to_rtf(text),
            )
    return output.getvalue()
