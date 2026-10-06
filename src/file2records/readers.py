"""Paper file -> ordered text chunks, for every format a researcher is likely to have.

Publishers deliver full text in more than one shape. Elsevier's text-mining API serves its own
XML, PubMed Central and Europe PMC serve JATS XML, a saved article page is HTML, a thesis chapter
is a Word file -- and a PDF is what is left when nothing better is available. The structured
formats are worth reading directly rather than printing to PDF and parsing back: their tables
arrive as rows and cells instead of whatever a layout model recovers from a picture of them, and
reading them needs no machine-learning model at all.

Every reader returns the same thing: a list of text blocks in document order (headings,
paragraphs, tables as markdown) and whatever metadata the file states about itself. parse()
turns the blocks into the {id, text} chunks the rest of the pipeline cites.

The format is decided by looking at the file, not trusting its name: Europe PMC's JATS has no
DOCTYPE line, publishers save HTML as .xml, and anything can be called .txt.
"""
import re
import uuid
from pathlib import Path

NS = uuid.UUID("a3f1c9d2-6b4e-4a7b-9e2d-5c8f1a6b4e7d")   # same namespace as parsing.py's PDF chunks

SUFFIXES = {".pdf", ".xml", ".nxml", ".html", ".htm", ".xhtml", ".docx", ".md", ".markdown", ".txt"}

# What each format is called wherever a person reads it.
LABELS = {"pdf": "PDF", "elsevier": "Elsevier XML", "jats": "JATS XML", "html": "HTML",
          "docx": "Word", "markdown": "Markdown", "text": "Text", "xml": "XML (general reader)"}

DOI = re.compile(r"\b(10\.\d{4,9}/[^\s\"'<>]+)")


class UnsupportedFile(ValueError):
    pass


# ---------- shared helpers ----------

def tidy(text: str | None) -> str:
    return re.sub(r"[ \t  ]+", " ", (text or "").replace("\n", " ")).strip()


def find_doi(text: str) -> str:
    m = DOI.search(text or "")
    return m.group(1).rstrip(".,;)]") if m else ""


def markdown_table(rows: list[list[str]], heading: str = "", notes: str = "") -> str | None:
    """Rows of cell text as one markdown table, its caption above and its footnotes below.

    Footnotes stay in the same chunk as the table on purpose. Chemistry tables routinely state
    the conditions every row shares in a footnote ("PET 2 g, EG 22 g, 190 °C"), and a row cut
    off from its footnote is a record with half its values missing.
    """
    rows = [[c.replace("|", "\\|") for c in r] for r in rows if any(c.strip() for c in r)]
    if not rows:
        return None
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    lines = [f"| {' | '.join(rows[0])} |", "|" + "|".join([" --- "] * width) + "|"]
    lines += [f"| {' | '.join(r)} |" for r in rows[1:]]
    return "\n".join(x for x in (heading, "\n".join(lines), notes) if x)


def split_long(text: str, limit: int = 2800) -> list[str]:
    """Keep chunks reviewable. Tables are never split; a row must stay with its header."""
    if len(text) <= limit or "\n| " in text or text.lstrip().startswith("|"):
        return [text]
    parts, current = [], ""
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        if current and len(current) + len(sentence) + 1 > limit:
            parts.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        parts.append(current)
    return parts


# ---------- format detection ----------

def detect(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix not in SUFFIXES:
        raise UnsupportedFile(f"{path.name}: unsupported file type. Supported: "
                              f"{', '.join(sorted(SUFFIXES))}")
    head = path.read_bytes()[:4096]
    if head.startswith(b"%PDF"):
        return "pdf"
    if suffix == ".pdf":
        raise UnsupportedFile(f"{path.name} is named .pdf but is not a PDF file.")
    if head.startswith(b"PK"):
        if suffix == ".docx":
            return "docx"
        raise UnsupportedFile(f"{path.name} is a zip archive, not a paper. Unzip it first.")
    if suffix in (".md", ".markdown"):
        return "markdown"
    if suffix == ".txt":
        return "text"
    if suffix == ".docx":
        raise UnsupportedFile(f"{path.name} is named .docx but is not a Word file.")
    sniff = head.decode("utf-8", errors="ignore").lower()
    if "full-text-retrieval-response" in sniff or "elsevier.com/xml/" in sniff:
        return "elsevier"
    if "<html" in sniff or suffix in (".html", ".htm", ".xhtml"):
        return "html"
    if re.search(r"jats|nlm//dtd|<article[\s>]", sniff):
        return "jats"
    return "xml"


# ---------- XML: Elsevier, JATS, and anything else ----------

def _xml_root(path: Path):
    from lxml import etree
    parser = etree.XMLParser(recover=True, resolve_entities=False, no_network=True, huge_tree=True)
    root = etree.parse(str(path), parser).getroot()
    if root is None:
        raise UnsupportedFile(f"{path.name} is not readable XML.")
    return root


def _local(element) -> str:
    tag = element.tag
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def _flatten(element, skip: set[str]) -> str:
    """All text under an element, inline markup dissolved into the sentence -- so
    [P<inf>66614</inf>]-ZnO reads [P66614]-ZnO rather than three fragments."""
    pieces = [element.text or ""]
    for child in element:
        if _local(child) not in skip:
            pieces.append(_flatten(child, skip))
        pieces.append(child.tail or "")
    return "".join(pieces)


def _rows(table, row_tag: str, cell_tags: set[str], skip: set[str]) -> list[list[str]]:
    rows = []
    for row in table.iter():
        if _local(row) == row_tag:
            rows.append([tidy(_flatten(c, skip)) for c in row if _local(c) in cell_tags])
    return rows


def _first(root, name: str):
    return next((e for e in root.iter() if _local(e) == name), None)


def _text_of(root, name: str, skip: set[str] = frozenset()) -> str:
    element = _first(root, name)
    return tidy(_flatten(element, skip)) if element is not None else ""


# Elsevier full-text XML (the ScienceDirect article API). Ported from the converter that built
# the PET depolymerisation corpus, with table footnotes kept.
ELS_SKIP = {"bibliography", "reference", "ref-info", "author-group", "affiliation",
            "correspondence", "cross-ref", "cross-refs", "further-reads", "acknowledgment",
            "alt-text", "link", "objects", "scopus-id", "scopus-eid", "doi", "pii"}


def _elsevier_table(table) -> str | None:
    label = next((tidy(_flatten(c, ELS_SKIP)) for c in table if _local(c) == "label"), "")
    caption = next((tidy(_flatten(c, ELS_SKIP)) for c in table.iter()
                    if _local(c) in ("caption", "simple-para")), "")
    notes = " ".join(tidy(_flatten(c, ELS_SKIP)) for c in table.iter()
                     if _local(c) in ("table-footnote", "legend"))
    heading = " ".join(x for x in (label, caption) if x)
    return markdown_table(_rows(table, "row", {"entry"}, ELS_SKIP), heading, notes)


def read_elsevier(path: Path) -> tuple[list[str], dict]:
    root = _xml_root(path)
    meta = {"doi": _text_of(root, "doi"), "title": _text_of(root, "title"),
            "journal": _text_of(root, "publicationName"),
            "year": _text_of(root, "coverDate")[:4]}
    blocks = [meta["title"]] if meta["title"] else []
    abstract = _text_of(root, "description", ELS_SKIP)
    if abstract:
        blocks.append("Abstract\n" + abstract)

    body = _first(root, "originalText")
    if body is None:
        raise UnsupportedFile(f"{path.name} is Elsevier XML without the article text (only the "
                              f"metadata). Request the FULL view from the article API.")
    for element in body.iter():
        tag = _local(element)
        if tag == "section-title":
            if text := tidy(_flatten(element, ELS_SKIP)):
                blocks.append("## " + text)
        elif tag in ("para", "simple-para"):
            ancestors = {_local(a) for a in element.iterancestors()}
            if ancestors & {"para", "simple-para", "table", "table-footnote", "caption",
                            "legend", "figure", "abstract", "bibliography"}:
                continue                    # covered by its parent, its table, or skipped
            text = tidy(_flatten(element, ELS_SKIP))
            if len(text) > 1:
                blocks.append(text)
        elif tag == "table":
            if rendered := _elsevier_table(element):
                blocks.append(rendered)
    if not any(b for b in blocks if not b.startswith(("## ", "Abstract\n")) and b != meta["title"]):
        # Older scanned articles carry only an unstructured <xocs:rawtext>: no paragraphs, no
        # tables, one long string. It is still the paper, so read it rather than refuse it.
        raw = _text_of(body, "rawtext")
        blocks += [raw] if raw else []
    return blocks, meta


# JATS: PubMed Central, Europe PMC, and the many publishers that deliver it (RSC, Springer
# Nature, MDPI, Frontiers, Beilstein, PLOS...).
JATS_SKIP = {"table-wrap", "fig", "ref-list", "fn-group", "ack", "alternatives", "graphic",
             "inline-graphic", "media", "supplementary-material", "table-wrap-foot"}


def _jats_table(wrap) -> str | None:
    skip = JATS_SKIP - {"table-wrap", "table-wrap-foot"}
    label = next((tidy(_flatten(c, skip)) for c in wrap if _local(c) == "label"), "")
    caption = next((tidy(_flatten(c, skip)) for c in wrap if _local(c) == "caption"), "")
    notes = " ".join(tidy(_flatten(c, skip)) for c in wrap if _local(c) == "table-wrap-foot")
    heading = " ".join(x for x in (label, caption) if x)
    return markdown_table(_rows(wrap, "tr", {"th", "td"}, skip), heading, notes)


def read_jats(path: Path) -> tuple[list[str], dict]:
    root = _xml_root(path)
    front = _first(root, "article-meta")
    if front is None:
        front = root
    doi = next((tidy(e.text) for e in front.iter()
                if _local(e) == "article-id" and e.get("pub-id-type") == "doi"), "")
    meta = {"doi": doi, "title": _text_of(front, "article-title"),
            "journal": _text_of(root, "journal-title"), "year": _text_of(front, "year")}
    blocks = [meta["title"]] if meta["title"] else []
    abstract = _first(front, "abstract")
    if abstract is not None:
        blocks.append("Abstract\n" + tidy(_flatten(abstract, JATS_SKIP)))

    seen = set()
    for part in (p for p in root if _local(p) in ("body", "floats-group")):
        for element in part.iter():
            tag = _local(element)
            ancestors = {_local(a) for a in element.iterancestors()}
            if ancestors & {"table-wrap", "fig", "ref-list", "ack", "fn-group"}:
                continue
            if tag == "title" and _local(element.getparent()) == "sec":
                if text := tidy(_flatten(element, JATS_SKIP)):
                    blocks.append("## " + text)
            elif tag == "p" and "p" not in ancestors:
                text = tidy(_flatten(element, JATS_SKIP))
                if len(text) > 1:
                    blocks.append(text)
            elif tag == "table-wrap" and id(element) not in seen:
                seen.add(id(element))
                if rendered := _jats_table(element):
                    blocks.append(rendered)
    if not any(b for b in blocks[1:] if not b.startswith("Abstract")):
        raise UnsupportedFile(f"{path.name} has no article body -- probably an abstract-only "
                              f"record. Europe PMC serves full text only for open-access papers.")
    return blocks, meta


def read_xml(path: Path) -> tuple[list[str], dict]:
    """Any other XML: paragraph- and heading-like elements in order, tables of either common
    shape (HTML tr/td or CALS row/entry). Labelled as the general reader wherever the format is
    shown, so nobody mistakes it for one that knows the publisher's layout."""
    root = _xml_root(path)
    blocks, seen = [], set()
    for element in root.iter():
        tag = _local(element).lower()
        if any(id(a) in seen for a in element.iterancestors()):
            continue
        if tag in ("table", "tgroup"):
            seen.add(id(element))
            rows = _rows(element, "tr", {"th", "td"}, set()) or _rows(element, "row", {"entry"}, set())
            if rendered := markdown_table(rows):
                blocks.append(rendered)
        elif tag in ("p", "para", "simple-para", "title", "caption", "h1", "h2", "h3", "li"):
            seen.add(id(element))
            if text := tidy(_flatten(element, set())):
                blocks.append(text)
    if not blocks:
        blocks = [b for b in (tidy(t) for t in re.split(r"\n\s*\n", "".join(root.itertext()))) if b]
    meta = {"doi": find_doi(" ".join(blocks[:20])), "title": ""}
    return blocks, meta


# ---------- HTML, Word, plain text ----------

def read_html(path: Path) -> tuple[list[str], dict]:
    from lxml import html
    root = html.fromstring(path.read_bytes())
    for junk in root.xpath("//script|//style|//nav|//header|//footer|//noscript|//form"):
        junk.drop_tree()

    def metatag(*names):
        for name in names:
            found = root.xpath(f'//meta[@name="{name}"]/@content')
            if found:
                return tidy(found[0])
        return ""

    meta = {"doi": metatag("citation_doi", "dc.identifier", "DC.identifier"),
            "title": metatag("citation_title", "dc.title") or tidy(root.findtext(".//title")),
            "journal": metatag("citation_journal_title"),
            "year": metatag("citation_publication_date", "citation_date")[:4]}
    meta["doi"] = find_doi(meta["doi"]) or meta["doi"]

    # The title first, as the XML readers do, so a search over the text finds what it says.
    blocks, seen = ([meta["title"]] if meta["title"] else []), set()
    for element in root.iter():
        if not isinstance(element.tag, str) or any(id(a) in seen for a in element.iterancestors()):
            continue
        tag = element.tag.lower()
        if tag == "table":
            seen.add(id(element))
            caption = tidy(element.findtext(".//caption"))
            rows = [[tidy(c.text_content()) for c in tr if c.tag in ("td", "th")]
                    for tr in element.iter("tr")]
            if rendered := markdown_table(rows, caption):
                blocks.append(rendered)
        elif tag in ("h1", "h2", "h3", "h4"):
            seen.add(id(element))
            if text := tidy(element.text_content()):
                blocks.append("## " + text)
        elif tag in ("p", "li", "figcaption"):
            seen.add(id(element))
            if len(text := tidy(element.text_content())) > 1:
                blocks.append(text)
    if not meta["doi"]:
        meta["doi"] = find_doi(" ".join(blocks[:20]))
    return blocks, meta


def read_docx(path: Path) -> tuple[list[str], dict]:
    import docx
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    document = docx.Document(str(path))
    blocks = []
    for child in document.element.body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            paragraph = Paragraph(child, document)
            text = tidy(paragraph.text)
            if not text:
                continue
            style = (paragraph.style.name if paragraph.style is not None else "") or ""
            blocks.append("## " + text if style.lower().startswith(("heading", "title")) else text)
        elif tag == "tbl":
            table = Table(child, document)
            rows = [[tidy(cell.text) for cell in row.cells] for row in table.rows]
            if rendered := markdown_table(rows):
                blocks.append(rendered)
    meta = {"doi": find_doi(" ".join(blocks[:20])), "title": tidy(document.core_properties.title)}
    return blocks, meta


def read_text(path: Path) -> tuple[list[str], dict]:
    """Markdown or plain text: blank-line separated blocks, a markdown table kept whole."""
    text = path.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]
    return blocks, {"doi": find_doi(" ".join(blocks[:20])), "title": ""}


READERS = {"elsevier": read_elsevier, "jats": read_jats, "xml": read_xml, "html": read_html,
           "docx": read_docx, "markdown": read_text, "text": read_text}


def parse(path: Path, paper_id: str) -> tuple[list[dict], dict, str]:
    """(chunks, meta, format) for any supported file. PDFs go to docling via parsing.py."""
    fmt = detect(path)
    if fmt == "pdf":
        from .parsing import parse_pdf_with_meta
        chunks, meta = parse_pdf_with_meta(path, paper_id)
        return chunks, meta, fmt
    blocks, meta = READERS[fmt](path)
    texts = [piece for block in blocks for piece in split_long(block) if piece.strip()]
    if not texts:
        raise UnsupportedFile(f"{path.name}: no text found in this {LABELS[fmt]} file.")
    chunks = [{"id": str(uuid.uuid5(NS, f"{paper_id}|{i}|{t}")), "text": t}
              for i, t in enumerate(texts)]
    return chunks, {k: v for k, v in meta.items() if v}, fmt
