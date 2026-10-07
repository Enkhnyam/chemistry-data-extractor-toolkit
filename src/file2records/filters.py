"""Choose papers by what their full text says, with a regular expression.

One idea, used everywhere a set of papers is chosen: search shows which papers match and where,
extraction and judging can be limited to them, and an export can be limited to their records.
`only` keeps papers whose text matches; `exclude` then drops papers whose text matches -- the
second matters as much as the first, because "PET" is also positron emission tomography and
"glycolysis" is also sugar metabolism.

Matching runs over the parsed text, so it costs nothing and needs no model.
"""
import re

from . import storage
from .storage import read_json

SNIPPET = 90          # characters of context either side of a match
MAX_SNIPPETS = 3      # per paper; enough to judge relevance at a glance


def compile_pattern(pattern: str, ignore_case: bool = True) -> re.Pattern:
    """The pattern, or a ValueError that says what is wrong with it in words."""
    if not pattern or not pattern.strip():
        raise ValueError("The search pattern is empty.")
    try:
        return re.compile(pattern, re.IGNORECASE if ignore_case else 0)
    except re.error as e:
        raise ValueError(f"Not a valid regular expression: {e}. Characters such as ( [ + * ? "
                         f"have special meanings; put a backslash before one to match it "
                         f"literally, e.g. \\(.") from e


def _full_text(paper: dict) -> str:
    return "\n\n".join(c["text"] for c in paper.get("chunks", []))


def _paper(pid: str) -> dict:
    return read_json(storage.PARSED / f"{pid}.json", {}) or {}


def select(paper_ids: list[str], only: str | None = None, exclude: str | None = None,
           ignore_case: bool = True) -> list[str]:
    """The papers among `paper_ids` that match `only` (if given) and not `exclude` (if given)."""
    keep = compile_pattern(only, ignore_case) if only else None
    drop = compile_pattern(exclude, ignore_case) if exclude else None
    chosen = []
    for pid in paper_ids:
        text = _full_text(_paper(pid))
        if keep and not keep.search(text):
            continue
        if drop and drop.search(text):
            continue
        chosen.append(pid)
    return chosen


def search(pattern: str, ignore_case: bool = True, paper_ids: list[str] | None = None) -> list[dict]:
    """Every paper whose text matches, most matches first, with a few snippets of context and
    the chunk each snippet is in -- so the review page can jump straight to it."""
    regex = compile_pattern(pattern, ignore_case)
    ids = paper_ids if paper_ids is not None else [p.stem for p in sorted(storage.PARSED.glob("*.json"))]
    hits = []
    for pid in ids:
        paper = _paper(pid)
        count, snippets = 0, []
        for chunk in paper.get("chunks", []):
            for m in regex.finditer(chunk["text"]):
                count += 1
                if len(snippets) < MAX_SNIPPETS:
                    text = chunk["text"]
                    start, end = max(0, m.start() - SNIPPET), min(len(text), m.end() + SNIPPET)
                    snippets.append({
                        "chunk_id": chunk["id"],
                        "before": ("…" if start else "") + text[start:m.start()],
                        "match": m.group(0),
                        "after": text[m.end():end] + ("…" if end < len(text) else ""),
                    })
        if count:
            hits.append({"id": pid, "filename": paper.get("filename", pid),
                         "title": (paper.get("meta") or {}).get("title", ""),
                         "matches": count, "snippets": snippets})
    return sorted(hits, key=lambda h: -h["matches"])
