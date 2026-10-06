"""The `file2records` command.

    file2records serve my-review                 the web app on that project folder
    file2records add my-review papers/           read files and folders into it
    file2records papers my-review                what is in it
    file2records search my-review "glycoly[sz]is"
    file2records check my-review                 what is missing before a run
    file2records extract my-review --only "glycoly[sz]is" --exclude "positron|tomograph"
    file2records judge my-review
    file2records export my-review dataset.csv    (.csv, .json, or .zip for the full bundle)

Every command takes the project folder first. Model commands use the model chosen in the web
app's Settings unless --model is given: any litellm model string, or rwth/<name> for RWTH's
KI:connect (key from RWTH_API_KEY).
"""
import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from . import __version__


def _project(folder):
    from .project import Project
    project = Project(folder)
    # Keys saved through the web app live in the project's .env; a .env in the current folder
    # is read too. Neither overrides a variable already set in the shell.
    load_dotenv(project.path / ".env")
    load_dotenv(Path.cwd() / ".env")
    return project


def _filters(p):
    p.add_argument("--only", metavar="REGEX",
                   help="only papers whose full text matches this regular expression")
    p.add_argument("--exclude", metavar="REGEX",
                   help="skip papers whose full text matches this regular expression")


def _print_result(r):
    name = r.get("filename") or r["id"]
    if r.get("error"):
        print(f"  ✗ {name}: {r['error']}")
    elif "n_chunks" in r:
        doi = f"  doi:{r['doi']}" if r.get("doi") else ""
        print(f"  ✓ {name}  [{r['format']}]  {r['n_chunks']} chunks{doi}")
    elif "n_records" in r:
        print(f"  ✓ {name}: {r['n_records']} records in {r['seconds']}s")
    else:
        print(f"  ✓ {name}: {r['n_verdicts']} verdicts in {r['seconds']}s")


def cmd_serve(args):
    os.environ["WORKSPACE_DIR"] = str(Path(args.folder).resolve())
    _project(args.folder)                        # creates the folder, opens it
    import uvicorn
    from .main import app
    url = f"http://{args.host}:{args.port}"
    print(f"file2records {__version__} — project {Path(args.folder).resolve()}\nOpen {url}")
    if not args.no_browser:
        import threading
        import webbrowser
        threading.Timer(1.0, webbrowser.open, [url]).start()
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


def cmd_add(args):
    project = _project(args.folder)
    print(f"Reading into {project.path}")
    results = project.add(*args.paths, source_tracking=not args.no_source_tracking,
                          on_file=_print_result)
    failed = sum(1 for r in results if r.get("error"))
    print(f"{len(results) - failed} added, {failed} failed")
    return 1 if failed and failed == len(results) else 0


def cmd_papers(args):
    papers = _project(args.folder).papers()
    if not papers:
        print("No papers yet. Add some:  file2records add <folder> <files or folders>")
    for p in papers:
        state = "judged" if p["judged"] else "extracted" if p["extracted"] else "parsed"
        records = "" if p["n_records"] is None else f"{p['n_records']} records"
        print(f"{p['id']:50.50}  {p['format']:8}  {state:9}  {records:11}  {p['doi']}")


def cmd_search(args):
    hits = _project(args.folder).search(args.pattern, ignore_case=not args.case_sensitive)
    for h in hits:
        print(f"\n{h['filename']}  ({h['matches']} matches)")
        for s in h["snippets"]:
            print(f"    …{s['before'][-60:]}[{s['match']}]{s['after'][:60]}…".replace("\n", " "))
    total = sum(h["matches"] for h in hits)
    print(f"\n{len(hits)} papers, {total} matches")


def cmd_check(args):
    project = _project(args.folder)
    ok = True
    for stage in ("extract", "judge"):
        missing = project.check(stage, args.model)
        ok &= stage == "judge" or not missing
        print(f"{stage}: {'ready' if not missing else 'not ready'}")
        for m in missing:
            print(f"  - {m}")
    return 0 if ok else 1


def _run_stage(args, stage):
    project = _project(args.folder)
    run = project.extract if stage == "extract" else project.judge
    results = run(args.model, only=args.only, exclude=args.exclude, redo=args.redo,
                  on_paper=_print_result)
    if not results:
        print(f"Nothing to {stage}: every chosen paper is done already (--redo to run again).")
    failed = sum(1 for r in results if r.get("error"))
    print(f"{len(results) - failed} done, {failed} failed")
    return 1 if failed else 0


def cmd_export(args):
    path = _project(args.folder).export(args.output, only=args.only, exclude=args.exclude,
                                        include_text=args.include_text,
                                        include_files=args.include_files)
    print(f"Wrote {path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="file2records",
        description="Turn papers (PDF, XML, HTML, Word, Markdown) into a structured dataset.")
    parser.add_argument("--version", action="version", version=f"file2records {__version__}")
    sub = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    p = sub.add_parser("serve", help="open the web app on a project folder")
    p.add_argument("folder", nargs="?", default="workspace")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--host", default="127.0.0.1",
                   help="keep the default unless you know why: the app has no login")
    p.add_argument("--no-browser", action="store_true")
    p.set_defaults(func=cmd_serve)

    p = sub.add_parser("add", help="read files or folders of papers into a project")
    p.add_argument("folder")
    p.add_argument("paths", nargs="+")
    p.add_argument("--no-source-tracking", action="store_true",
                   help="don't tag chunks, so records won't cite the passage they came from")
    p.set_defaults(func=cmd_add)

    p = sub.add_parser("papers", help="list the papers in a project")
    p.add_argument("folder")
    p.set_defaults(func=cmd_papers)

    p = sub.add_parser("search", help="search the full text of every paper with a regex")
    p.add_argument("folder")
    p.add_argument("pattern")
    p.add_argument("--case-sensitive", action="store_true")
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("check", help="say what is missing before a run")
    p.add_argument("folder")
    p.add_argument("--model")
    p.set_defaults(func=cmd_check)

    for stage, text in (("extract", "extract records from papers not extracted yet"),
                        ("judge", "audit extracted records with a second model")):
        p = sub.add_parser(stage, help=text)
        p.add_argument("folder")
        p.add_argument("--model", help='litellm model string, or rwth/<name> '
                                       '(default: the model chosen in Settings)')
        p.add_argument("--redo", action="store_true", help="also re-run papers already done")
        _filters(p)
        p.set_defaults(func=lambda a, s=stage: _run_stage(a, s))

    p = sub.add_parser("export", help="write records to .csv / .json, or a .zip bundle")
    p.add_argument("folder")
    p.add_argument("output")
    p.add_argument("--include-text", action="store_true",
                   help="put the paper text in a .zip bundle (check the papers' licences)")
    p.add_argument("--include-files", action="store_true",
                   help="put the source files in a .zip bundle (check the papers' licences)")
    _filters(p)
    p.set_defaults(func=cmd_export)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args) or 0
    except (ValueError, RuntimeError, FileNotFoundError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
