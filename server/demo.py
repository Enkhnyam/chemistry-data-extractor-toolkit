"""The demo workspace: two open-access papers, already parsed, extracted and judged.

A fresh clone used to open on an empty app behind an eight-step checklist, which is a poor way
to find out what the thing does. It now opens on a finished project -- two papers, their records,
the judge's verdicts on them, a full report -- so the first thing a new user sees is the output,
and the only thing they have to supply to make it *theirs* is an API key.

Three rules this seeding follows, because the alternative caused a real bug once:

1. It writes files, it is never a fallback. `config.get_schema()` and `config._get_text()` still
   return empty when nothing is saved -- the docstrings there explain why, and they are right. A
   default that appears when a field is blank silently extracts somebody else's chemistry from
   your papers and looks like it worked. Here the schema and the prompts are written to disk as
   real values, so what the Settings page shows is exactly what a run will use.

2. It happens once, into an empty workspace only. `seed_if_empty()` is a no-op the moment there
   is anything of the user's there, so it cannot overwrite work or come back after `clear()`.

3. It is announced and reversible. `state()` tells the interface the workspace is the demo, so it
   can say so, and `clear()` removes it whole.
"""
import shutil
from pathlib import Path

from .storage import WORKSPACE, PDFS, PARSED, EXTRACTED, JUDGED, CONFIG, read_json, write_json

DEMO = Path(__file__).resolve().parents[1] / "demo"
STAGES = {"pdfs": PDFS, "parsed": PARSED, "extracted": EXTRACTED, "judged": JUDGED,
          "config": CONFIG}
# Written into the workspace when the demo is seeded and deleted when it is cleared, so "is this
# the demo?" is a question about the workspace rather than a guess from what it happens to hold.
MARKER = WORKSPACE / ".demo"


def available() -> bool:
    return DEMO.is_dir() and any((DEMO / "pdfs").glob("*.pdf"))


def is_empty() -> bool:
    """Nothing of the user's here yet. A .gitkeep is not content."""
    for directory in STAGES.values():
        if any(p for p in directory.iterdir() if not p.name.startswith(".")):
            return False
    return True


def seed(*, replace: bool = False) -> bool:
    """Copy the demo into the workspace. Returns whether it did.

    `replace=True` empties the workspace first, and is only ever reached from someone pressing a
    button that says so. Everything else goes through seed_if_empty(), which will not touch a
    workspace that has anything in it.
    """
    if replace:
        clear()
    return _seed_if_empty()


def seed_if_empty() -> bool:
    """Copy the demo in, if and only if there is nothing to lose. Returns whether it did.

    TOOLKIT_SEED_DEMO=0 turns it off. The smoke tests set it: most of what they assert is what an
    *empty* workspace does -- prompts start blank, a stage refuses to run, a failed parse leaves
    no orphan PDF -- and a workspace seeded underneath them is testing the demo instead.
    """
    import os
    if os.environ.get("TOOLKIT_SEED_DEMO", "1") == "0":
        return False
    return _seed_if_empty()


def _seed_if_empty() -> bool:
    if not available() or not is_empty():
        return False
    for name, target in STAGES.items():
        source = DEMO / name
        if not source.is_dir():
            continue
        for item in source.iterdir():
            if item.is_file() and not item.name.startswith("."):
                shutil.copy2(item, target / item.name)
    MARKER.write_text("Seeded from demo/. Delete this file, or use Clear demo, to disown it.\n",
                      encoding="utf-8")
    return True


def state() -> dict:
    """What the interface needs to say about the workspace it is showing."""
    return {"is_demo": MARKER.exists(), "available": available(), "workspace_empty": is_empty(),
            "papers": sorted(p.name for p in (DEMO / "pdfs").glob("*.pdf")) if available() else []}


def clear() -> None:
    """Empty the workspace. Used to start a real project, so it takes the config too -- a schema
    left behind from the demo is the silent default this design exists to avoid."""
    for directory in STAGES.values():
        for item in directory.iterdir():
            if item.name.startswith("."):
                continue
            shutil.rmtree(item) if item.is_dir() else item.unlink()
    MARKER.unlink(missing_ok=True)
