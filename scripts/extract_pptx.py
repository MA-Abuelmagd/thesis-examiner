#!/usr/bin/env python3
"""Extract per-slide text + speaker notes from a .pptx. Stdlib only.

Usage: extract_pptx.py DECK.pptx [--json]
Exit 0 on success; exit 2 with "ERROR: ..." on unreadable/empty deck.
"""
import json, posixpath, re, sys, zipfile
import xml.etree.ElementTree as ET

A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"
TITLE_TYPES = {"title", "ctrTitle"}
MAX_PART_BYTES = 10 * 1024 * 1024

def safe_fromstring(xml_bytes):
    """OOXML parts must not contain DTDs — reject them (XXE/billion-laughs guard)."""
    if len(xml_bytes) > MAX_PART_BYTES:
        raise ET.ParseError("part too large")
    if b"<!DOCTYPE" in xml_bytes or b"<!ENTITY" in xml_bytes:
        raise ET.ParseError("DTD/entity declarations are not allowed in OOXML parts")
    return ET.fromstring(xml_bytes)

def read_part(z, name):
    """z.read with failures normalized to ET.ParseError. Checks the DECLARED
    uncompressed size before reading so a zip bomb is never decompressed."""
    try:
        info = z.getinfo(name)
    except KeyError:
        raise ET.ParseError(f"missing part: {name}")
    if info.file_size > MAX_PART_BYTES:
        raise ET.ParseError(f"part too large: {name}")
    return z.read(name)

def rels_map(z, part):
    """Relationship Id -> (normalized Target part name, Type) for one part's .rels.
    Raises ET.ParseError if the rels part is absent or unparseable."""
    part_dir = posixpath.dirname(part)
    rels_name = posixpath.join(part_dir, "_rels", posixpath.basename(part) + ".rels")
    root = safe_fromstring(read_part(z, rels_name))
    out = {}
    for rel in root.iter(REL + "Relationship"):
        rid, target = rel.get("Id"), rel.get("Target", "")
        if not rid or not target:
            continue
        if target.startswith("/"):  # package-absolute target
            name = target.lstrip("/")
        else:  # relative to the source part's directory ("../notesSlides/..." etc.)
            name = posixpath.normpath(posixpath.join(part_dir, target))
        out[rid] = (name, rel.get("Type", ""))
    return out

def ordered_slide_parts(z):
    """[(display_n, slide_part, notes_part_or_None)] in p:sldIdLst order, resolved
    through the OOXML relationship graph (part filenames carry no order guarantee:
    PowerPoint preserves part names across reorders/insertions). Returns None when
    presentation.xml or its rels are absent/unparseable, so the caller can fall
    back to filename-number ordering."""
    try:
        rels = rels_map(z, "ppt/presentation.xml")
        pres = safe_fromstring(read_part(z, "ppt/presentation.xml"))
    except ET.ParseError:
        return None
    parts = [rels[rid][0] for sld in pres.iter(P + "sldId")
             if (rid := sld.get(R + "id")) in rels]
    if not parts:
        return None
    ordered = []
    for n, part in enumerate(parts, 1):
        notes = None
        try:
            slide_rels = rels_map(z, part)
        except ET.ParseError:
            slide_rels = {}
        for target, rtype in slide_rels.values():
            if rtype.endswith("/notesSlide"):
                notes = target
                break
        ordered.append((n, part, notes))
    return ordered

def shape_paragraphs(sp):
    """List of paragraph strings in one shape (runs joined, empty dropped)."""
    out = []
    for para in sp.iter(A + "p"):
        text = "".join(t.text or "" for t in para.iter(A + "t")).strip()
        if text:
            out.append(text)
    return out

def parse_slide(xml_bytes):
    root = safe_fromstring(xml_bytes)
    title, body = "", []
    for sp in root.iter(P + "sp"):
        ph = sp.find(f"{P}nvSpPr/{P}nvPr/{P}ph")
        ptype = ph.get("type", "") if ph is not None else ""
        paras = shape_paragraphs(sp)
        if not paras:
            continue
        if ptype in TITLE_TYPES and not title:
            title = paras[0]
            body.extend(paras[1:])
        else:
            body.extend(paras)
    return title, body

def main():
    args = [a for a in sys.argv[1:] if a != "--json"]
    as_json = "--json" in sys.argv
    if len(args) != 1:
        print("ERROR: usage: extract_pptx.py DECK.pptx [--json]", file=sys.stderr); return 2
    try:
        z = zipfile.ZipFile(args[0])
    except (zipfile.BadZipFile, OSError) as e:
        print(f"ERROR: not a readable .pptx: {e}", file=sys.stderr); return 2
    ordered = ordered_slide_parts(z)
    if ordered is None:
        # Fallback (no readable presentation.xml + rels): filename-number order,
        # notesSlideN paired to slideN by the same N.
        slide_re = re.compile(r"^ppt/slides/slide(\d+)\.xml$")
        notes_re = re.compile(r"^ppt/notesSlides/notesSlide(\d+)\.xml$")
        slides, notes = {}, {}
        for name in z.namelist():
            m = slide_re.match(name)
            if m:
                slides[int(m.group(1))] = name
            m = notes_re.match(name)
            if m:
                notes[int(m.group(1))] = name
        ordered = [(n, slides[n], notes.get(n)) for n in sorted(slides)]
    if not ordered:
        print("ERROR: no slides found (image-only or not a presentation?)", file=sys.stderr); return 2
    result = []
    for n, slide_part, notes_part in ordered:
        try:
            title, body = parse_slide(read_part(z, slide_part))
        except ET.ParseError:
            title, body = "", ["[unparseable slide XML]"]
        note_text = ""
        if notes_part:
            try:
                _, nbody = parse_slide(read_part(z, notes_part))
                note_text = " ".join(nbody)
            except ET.ParseError:
                pass
        result.append({"n": n, "title": title, "body": body, "notes": note_text})
    if as_json:
        print(json.dumps({"slideCount": len(result), "slides": result}, ensure_ascii=False))
    else:
        for s in result:
            print(f"## Slide {s['n']}: {s['title']}".rstrip(": "))
            for line in s["body"]:
                print(f"- {line}")
            if s["notes"]:
                print(f"> Speaker notes: {s['notes']}")
            print()
    return 0

if __name__ == "__main__":
    sys.exit(main())
