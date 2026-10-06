"""Everything lives on disk under WORKSPACE_DIR, one JSON file per paper per stage.
No database: a researcher's corpus is a few hundred papers at most, and a directory of
JSON files is what they can inspect, back up, and diff without extra tooling."""
import hashlib
import json
import os
import re
from pathlib import Path

WORKSPACE = PDFS = PARSED = EXTRACTED = JUDGED = CONFIG = Path()


def use(path) -> Path:
    """Point every stage at the project folder `path`, creating it if needed.

    The folders are module attributes that the rest of the package reads at call time
    (`storage.PARSED`, never `from .storage import PARSED`), so switching projects is this one
    call. They used to be fixed at import and created as a side effect of importing -- which a
    web server can live with and a library cannot: `import file2records` made directories in
    whatever folder you happened to be standing in.

    `pdfs/` holds every source file, PDF or not. The name is kept so workspaces made by earlier
    versions open unchanged.
    """
    global WORKSPACE, PDFS, PARSED, EXTRACTED, JUDGED, CONFIG
    WORKSPACE = Path(path).expanduser().resolve()
    PDFS = WORKSPACE / "pdfs"
    PARSED = WORKSPACE / "parsed"
    EXTRACTED = WORKSPACE / "extracted"
    JUDGED = WORKSPACE / "judged"
    CONFIG = WORKSPACE / "config"
    for d in (PDFS, PARSED, EXTRACTED, JUDGED, CONFIG):
        d.mkdir(parents=True, exist_ok=True)
    return WORKSPACE


def default_workspace() -> Path:
    """WORKSPACE_DIR if set (Docker, tests), otherwise ./workspace."""
    return Path(os.environ.get("WORKSPACE_DIR") or Path.cwd() / "workspace")


def source_file(pid: str) -> Path | None:
    """The original file a paper was parsed from, whatever its format."""
    return next(iter(sorted(PDFS.glob(f"{pid}.*"))), None)


def read_json(path: Path, default=None):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", Path(name).stem).strip("-").lower()
    return slug or "paper"


def paper_id_for(filename: str, content: bytes) -> str:
    """Stable id from name + content, so re-uploading the same PDF lands on the same paper."""
    return f"{slugify(filename)}-{hashlib.sha1(content).hexdigest()[:8]}"


def spend_on(pid: str) -> dict:
    """What this paper has cost so far, across both model stages."""
    total = {"cost_usd": 0.0, "tokens": 0, "calls": 0}
    for directory in (EXTRACTED, JUDGED):
        usage = (read_json(directory / f"{pid}.json", {}) or {}).get("usage") or {}
        if not usage:
            continue
        total["cost_usd"] = round(total["cost_usd"] + usage.get("cost_usd", 0.0), 6)
        total["tokens"] += usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)
        total["calls"] += 1
    return total


def list_papers() -> list[dict]:
    papers = []
    for f in sorted(PARSED.glob("*.json")):
        meta = read_json(f, {})
        pid = f.stem
        papers.append({
            "id": pid,
            "filename": meta.get("filename", pid),
            # What the reader found in the file itself. Empty for papers parsed before readers
            # recorded it, and for PDFs whose first page names no DOI.
            "format": meta.get("format", "pdf"),
            "doi": (meta.get("meta") or {}).get("doi", ""),
            "title": (meta.get("meta") or {}).get("title", ""),
            "source_tracking": meta.get("source_tracking", True),
            "n_chunks": len(meta.get("chunks", [])),
            "extracted": (EXTRACTED / f"{pid}.json").exists(),
            "judged": (JUDGED / f"{pid}.json").exists(),
            # None when never extracted, 0 when extracted and empty -- the two look identical
            # in the UI otherwise, and they mean very different things.
            "n_records": (lambda d: None if d is None else len(d.get("records", [])))(
                read_json(EXTRACTED / f"{pid}.json")),
            "spend": spend_on(pid),
            # Which model produced each stage. Recorded since the beginning but never shown,
            # which made two runs of the same paper by different models indistinguishable
            # afterwards -- exactly the comparison anyone choosing a model needs to make.
            "models": {
                "extract": (read_json(EXTRACTED / f"{pid}.json", {}) or {}).get("model"),
                "judge": (read_json(JUDGED / f"{pid}.json", {}) or {}).get("model"),
            },
        })
    return papers


def require(path: Path, what: str) -> dict:
    data = read_json(path)
    if data is None:
        raise FileNotFoundError(f"{what} not found: {path.stem}")
    return data


def version_of(path: Path) -> str:
    """A token that changes whenever the file does, so a save can refuse to overwrite work it
    never saw. Cheaper and more honest than a hash: mtime_ns moves on every write.

    A string, not the integer it looks like. st_mtime_ns is around 1.8e18, and JavaScript's
    JSON.parse turns any number past 2^53 into the nearest float -- so the browser read this
    token, rounded it, sent the rounded value back, and every single save was rejected as a
    conflict with an edit that had never happened. Python's arbitrary-precision ints meant the
    API tests round-tripped it perfectly and saw nothing. As a string it is opaque to both
    sides and compared, correctly, for equality.
    """
    return str(path.stat().st_mtime_ns) if path.exists() else "0"
