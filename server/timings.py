"""How long each stage has actually taken here, so the UI can say "about 40s" instead of
leaving someone staring at a spinner wondering whether it has hung.

Estimates come from this machine's own history rather than a hardcoded guess: parsing speed
depends on the PDF, on whether OCR kicks in, and on whether there's a GPU, and no constant
we could ship would be right for more than one person's laptop.
"""
from statistics import median

from .storage import CONFIG, read_json, write_json

FILE = CONFIG / "timings.json"
KEEP = 20          # recent runs per stage; enough for a stable median, short enough to track change


def record(stage: str, seconds: float, size: int | None = None) -> None:
    history = read_json(FILE, {})
    runs = history.setdefault(stage, [])
    runs.append({"seconds": round(seconds, 2), "size": size})
    history[stage] = runs[-KEEP:]
    write_json(FILE, history)


def estimates() -> dict:
    """{stage: {seconds, per_unit, n}} -- per_unit is None until a sized run has been seen.

    per_unit is what makes an estimate travel between papers: a 200-chunk paper does not take
    the same time as a 20-chunk one, so the frontend multiplies per_unit by the size of the job
    it is about to start, and falls back to the flat median when it has no size to multiply.
    """
    history = read_json(FILE, {})
    out = {}
    for stage, runs in history.items():
        if not runs:
            continue
        sized = [r for r in runs if r.get("size")]
        out[stage] = {
            "seconds": round(median(r["seconds"] for r in runs), 1),
            "per_unit": round(median(r["seconds"] / r["size"] for r in sized), 3) if sized else None,
            "n": len(runs),
        }
    return out
