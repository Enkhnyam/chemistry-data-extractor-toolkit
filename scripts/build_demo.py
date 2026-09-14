"""Regenerate demo/parsed, demo/extracted and demo/judged from demo/pdfs.

The demo ships a finished project, which means it ships model output, which means that output
has to come from somewhere a reader can check. This is that somewhere: it runs the same three
functions the web app runs, against the same two PDFs, and writes the same files the app writes.
Nothing in demo/ is handwritten.

It also fixes the file names. The app stores a PDF as <paper_id>.pdf, where the id is derived
from the upload's filename and its bytes, so seeding a workspace with differently-named files
would produce papers whose PDF and parse do not match. The ids are computed here the same way.

    OPENAI_API_KEY=... .venv/bin/python scripts/build_demo.py            # all three stages
    .venv/bin/python scripts/build_demo.py --stage parse                 # just re-parse

Parsing is slow (docling, minutes per paper) and costs nothing; extraction and judging are one
model call each per paper and cost a few cents.
"""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DEMO = ROOT / "demo"
# Whatever model you have a key for. Defaults to a cheap OpenAI one so the command in the
# docstring works for anyone; set DEMO_MODEL and the matching credentials to use your own
# endpoint. The model that produced a file is recorded in the file, so the demo never implies
# its records came from somewhere they did not.
MODEL = os.environ.get("DEMO_MODEL", "gpt-4o-mini")


def call_params() -> dict:
    """Credentials for MODEL, read from the environment the same way the app reads .env."""
    prefix = "AZURE" if MODEL.startswith("azure/") else "OPENAI"
    params = {"model": MODEL, "api_key": os.environ.get(f"{prefix}_API_KEY", "")}
    for name, var in (("api_base", f"{prefix}_API_BASE"), ("api_version", f"{prefix}_API_VERSION")):
        if os.environ.get(var):
            params[name] = os.environ[var]
    if not params["api_key"]:
        sys.exit(f"no {prefix}_API_KEY in the environment")
    return params

# What each source PDF is called in the interface. Keyed by the file as it sits in demo/pdfs
# before renaming; the value is what a user would have seen had they uploaded it themselves.
SOURCES = {
    "liu-2021-cholinium-amino-acid-ils.pdf":
        "Amino Acid-Based Cholinium Ionic Liquids (ACS Sust. Chem. Eng. 2021).pdf",
    "yue-2013-lewis-acidic-ils.pdf":
        "Lewis Acidic Ionic Liquids for PET Glycolysis (Polymers 2013).pdf",
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["parse", "extract", "judge", "all"], default="all")
    args = ap.parse_args()

    # Imported late: importing server.storage creates the workspace directories, and pointing
    # WORKSPACE_DIR at demo/ first is what makes the app's own writers land here instead.
    os.environ["WORKSPACE_DIR"] = str(DEMO)
    from server import extraction, judge, parsing
    from server.storage import PDFS, PARSED, EXTRACTED, JUDGED, paper_id_for, read_json, write_json

    schema = json.loads((DEMO / "config/schema.json").read_text())["fields"]
    prompt = (DEMO / "config/extract_prompt.txt").read_text(encoding="utf-8")
    rubric = (DEMO / "config/judge_prompt.txt").read_text(encoding="utf-8")
    params = call_params()

    for stored_name, display_name in SOURCES.items():
        source = PDFS / stored_name
        content = source.read_bytes() if source.exists() else None
        if content is None:
            # Already renamed by a previous run: find it by matching the display name's id.
            candidates = [p for p in PDFS.glob("*.pdf")]
            source = next((p for p in candidates
                           if paper_id_for(display_name, p.read_bytes()) == p.stem), None)
            if source is None:
                sys.exit(f"missing: {stored_name}")
            content = source.read_bytes()
        pid = paper_id_for(display_name, content)
        target = PDFS / f"{pid}.pdf"
        if source != target:
            source.rename(target)
        print(f"\n{display_name}\n  id {pid}")

        if args.stage in ("parse", "all") or not (PARSED / f"{pid}.json").exists():
            chunks = parsing.parse_pdf(target, pid)
            write_json(PARSED / f"{pid}.json", {"id": pid, "filename": display_name,
                                                "source_tracking": True, "chunks": chunks})
            print(f"  parsed   {len(chunks)} chunks")

        paper = read_json(PARSED / f"{pid}.json")
        text = parsing.chunks_to_text(paper["chunks"], True)

        if args.stage in ("extract", "all"):
            records, usage = extraction.run_extraction(params, prompt, schema, [], text, True)
            write_json(EXTRACTED / f"{pid}.json",
                       {"id": pid, "records": records, "usage": usage, "model": MODEL})
            print(f"  extracted {len(records)} records  ${usage['cost_usd']:.4f}")

        if args.stage in ("judge", "all"):
            records = read_json(EXTRACTED / f"{pid}.json")["records"]
            verdicts, usage = judge.run_judge(params, rubric, text, records)
            write_json(JUDGED / f"{pid}.json",
                       {"id": pid, "verdicts": verdicts, "usage": usage, "model": MODEL,
                        "judged_records": records})
            print(f"  judged    {len(verdicts)} verdicts  ${usage['cost_usd']:.4f}")


if __name__ == "__main__":
    main()
