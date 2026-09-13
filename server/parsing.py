"""PDF -> stable-ID text chunks, via docling. Ported from the source project's
core/parse.py: same chunking (docling's own text/table items), same per-chunk UUID scheme,
so a chunk id means the same thing here as it does there. The only change is that a chunk
is kept as structured {id, text} instead of being flattened to "ID: <uuid>\\ntext" up front
-- the review UI needs the id and text separately, and chunks_to_text() re-flattens them for
the LLM call the same way."""
import uuid
from pathlib import Path

from docling.document_converter import DocumentConverter
from docling_core.types.doc import TableItem, TextItem
from markdown_it import MarkdownIt

NS = uuid.UUID("a3f1c9d2-6b4e-4a7b-9e2d-5c8f1a6b4e7d")

# Reaction conditions live in tables, so a review pane that shows a table as raw pipes is
# unreadable exactly where it matters most. html=False escapes any markup the PDF text
# happens to contain -- the chunk text is untrusted input, and it reaches the browser as HTML.
_MARKDOWN = MarkdownIt("commonmark", {"html": False}).enable("table")


def with_html(chunks: list[dict]) -> list[dict]:
    """Chunks plus a rendered `html` for each, for the review panes. Rendered on read rather
    than stored, so papers parsed before this existed render too."""
    return [{**c, "html": _MARKDOWN.render(c["text"])} for c in chunks]

_converter: DocumentConverter | None = None


def _get_converter() -> DocumentConverter:
    global _converter
    if _converter is None:
        _converter = DocumentConverter()
    return _converter


def parse_pdf(pdf_path: Path, paper_id: str) -> list[dict]:
    """[{id, text}, ...] for every table and text item docling finds, in document order."""
    doc = _get_converter().convert(str(pdf_path)).document
    chunks = []
    for i, (item, _) in enumerate(doc.iterate_items()):
        if isinstance(item, TableItem):
            text = item.export_to_markdown(doc).strip()
        elif isinstance(item, TextItem):
            text = (item.text or "").strip()
        else:
            continue
        if not text:
            continue
        cid = str(uuid.uuid5(NS, f"{paper_id}|{i}|{text}"))
        chunks.append({"id": cid, "text": text})
    return chunks


def chunks_to_text(chunks: list[dict], with_source: bool) -> str:
    """The blob sent to the LLM. Tagging every chunk with its id is what lets the model
    cite sources in source_chunk_ids -- so with_source=False must drop the tags entirely,
    not just hide the field, or the model teaches itself provenance from the prompt anyway."""
    if with_source:
        return "\n\n".join(f"ID: {c['id']}\n{c['text']}" for c in chunks)
    return "\n\n".join(c["text"] for c in chunks)
