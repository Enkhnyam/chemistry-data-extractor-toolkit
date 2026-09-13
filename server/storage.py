"""Everything lives on disk under WORKSPACE_DIR, one JSON file per paper per stage.
No database: a researcher's corpus is a few hundred papers at most, and a directory of
JSON files is what they can inspect, back up, and diff without extra tooling."""
import hashlib
import json
import os
import re
from pathlib import Path

WORKSPACE = Path(os.environ.get("WORKSPACE_DIR", Path(__file__).resolve().parents[1] / "workspace"))
PDFS = WORKSPACE / "pdfs"
PARSED = WORKSPACE / "parsed"
EXTRACTED = WORKSPACE / "extracted"
JUDGED = WORKSPACE / "judged"
CONFIG = WORKSPACE / "config"

for _d in (PDFS, PARSED, EXTRACTED, JUDGED, CONFIG):
    _d.mkdir(parents=True, exist_ok=True)


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
            "source_tracking": meta.get("source_tracking", True),
            "n_chunks": len(meta.get("chunks", [])),
            "extracted": (EXTRACTED / f"{pid}.json").exists(),
            "judged": (JUDGED / f"{pid}.json").exists(),
            # None when never extracted, 0 when extracted and empty -- the two look identical
            # in the UI otherwise, and they mean very different things.
            "n_records": (lambda d: None if d is None else len(d.get("records", [])))(
                read_json(EXTRACTED / f"{pid}.json")),
            "spend": spend_on(pid),
        })
    return papers


def require(path: Path, what: str) -> dict:
    data = read_json(path)
    if data is None:
        raise FileNotFoundError(f"{what} not found: {path.stem}")
    return data


def version_of(path: Path) -> int:
    """A token that changes whenever the file does, so a save can refuse to overwrite work it
    never saw. Cheaper and more honest than a hash: mtime_ns moves on every write."""
    return path.stat().st_mtime_ns if path.exists() else 0
