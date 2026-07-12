#!/usr/bin/env python3
"""Generate tests/tmp/sample.pptx — 3 slides with titles, bodies, and one notes slide."""
import sys, zipfile
from pathlib import Path

NS = ('xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
      'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"')

def sp(ph_type, *lines):
    paras = "".join(f"<a:p><a:r><a:t>{t}</a:t></a:r></a:p>" for t in lines)
    ph = f'<p:ph type="{ph_type}"/>' if ph_type else "<p:ph/>"
    return (f'<p:sp><p:nvSpPr><p:cNvPr id="1" name=""/><p:cNvSpPr/><p:nvPr>{ph}'
            f'</p:nvPr></p:nvSpPr><p:spPr/><p:txBody><a:bodyPr/>{paras}</p:txBody></p:sp>')

def slide(*shapes):
    return (f'<?xml version="1.0"?><p:sld {NS}><p:cSld><p:spTree>'
            f'{"".join(shapes)}</p:spTree></p:cSld></p:sld>')

def notes(*shapes):
    return (f'<?xml version="1.0"?><p:notes {NS}><p:cSld><p:spTree>'
            f'{"".join(shapes)}</p:spTree></p:cSld></p:notes>')

EVIL = ('<?xml version="1.0"?><!DOCTYPE bomb [<!ENTITY a "xx"><!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;">'
        '<!ENTITY c "&b;&b;&b;&b;&b;&b;&b;&b;">]>'
        f'<p:sld {NS}><p:cSld><p:spTree><p:sp><p:nvSpPr><p:cNvPr id="1" name=""/><p:cNvSpPr/>'
        '<p:nvPr><p:ph type="title"/></p:nvPr></p:nvSpPr><p:spPr/><p:txBody><a:bodyPr/>'
        '<a:p><a:r><a:t>&c;</a:t></a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld></p:sld>')

R_NS = 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
REL_NS = 'xmlns="http://schemas.openxmlformats.org/package/2006/relationships"'
NOTES_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/notesSlide"

def reordered(z):
    """PowerPoint-preserves-part-names scenario: sldIdLst order is slide3, slide1,
    slide2, and the FIRST-ordered slide (slide3.xml) carries the notes part —
    filename numbers agree with neither display order nor notes pairing."""
    z.writestr("ppt/presentation.xml",
               f'<?xml version="1.0"?><p:presentation {NS} {R_NS}><p:sldIdLst>'
               '<p:sldId id="258" r:id="rId3"/><p:sldId id="256" r:id="rId1"/>'
               '<p:sldId id="257" r:id="rId2"/></p:sldIdLst></p:presentation>')
    z.writestr("ppt/_rels/presentation.xml.rels",
               f'<?xml version="1.0"?><Relationships {REL_NS}>'
               '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide1.xml"/>'
               '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide2.xml"/>'
               '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide3.xml"/>'
               '</Relationships>')
    z.writestr("ppt/slides/slide1.xml", slide(sp("title", "Methods Slide One")))
    z.writestr("ppt/slides/slide2.xml", slide(sp("title", "Results Slide Two")))
    z.writestr("ppt/slides/slide3.xml", slide(sp("ctrTitle", "Reordered Opening")))
    z.writestr("ppt/slides/_rels/slide3.xml.rels",
               f'<?xml version="1.0"?><Relationships {REL_NS}>'
               f'<Relationship Id="rId2" Type="{NOTES_TYPE}" Target="../notesSlides/notesSlide3.xml"/>'
               '</Relationships>')
    z.writestr("ppt/notesSlides/notesSlide3.xml", notes(sp("body", "Opening notes travel with slide three.")))

BOMB_PARTS = {"ppt/slides/slide1.xml", "ppt/notesSlides/notesSlide2.xml"}

def declare_bomb(path, part_names):
    """Patch the central directory so the named parts DECLARE an uncompressed
    size over the extractor's 10 MB cap while staying tiny on disk — the shape
    a zip bomb presents to code that must decide before decompressing."""
    data = bytearray(path.read_bytes())
    i = 0
    while (i := data.find(b"PK\x01\x02", i)) != -1:
        name_len = int.from_bytes(data[i + 28:i + 30], "little")
        name = bytes(data[i + 46:i + 46 + name_len]).decode()
        if name in part_names:
            data[i + 24:i + 28] = (11 * 1024 * 1024).to_bytes(4, "little")  # uncompressed size
        i += 4
    path.write_bytes(bytes(data))

out = Path(sys.argv[1] if len(sys.argv) > 1 else "tests/tmp/sample.pptx")
evil = "--evil" in sys.argv
bomb = "--bomb" in sys.argv
out.parent.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(out, "w") as z:
    z.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
    if evil:
        z.writestr("ppt/slides/slide1.xml", EVIL)
    elif bomb:
        z.writestr("ppt/slides/slide1.xml", slide(sp("title", "Bomb Slide")))
        z.writestr("ppt/slides/slide2.xml", slide(sp("title", "Safe Slide")))
        z.writestr("ppt/notesSlides/notesSlide2.xml", notes(sp("body", "Oversized notes must be skipped.")))
    elif "--reordered" in sys.argv:
        reordered(z)
    else:
        z.writestr("ppt/slides/slide1.xml", slide(sp("ctrTitle", "Model X: A Better Approach"), sp("subTitle", "Defense Presentation")))
        z.writestr("ppt/slides/slide2.xml", slide(sp("title", "Results"), sp("body", "Accuracy: 97%", "Beats baseline by 12 points")))
        z.writestr("ppt/slides/slide3.xml", slide(sp("title", "Future Work"), sp("body", "Scale to production")))
        z.writestr("ppt/notesSlides/notesSlide2.xml", notes(sp("body", "Mention the ablation only if asked.")))
if bomb:
    declare_bomb(out, BOMB_PARTS)
print(out)
