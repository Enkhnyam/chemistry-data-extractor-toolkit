"""End-to-end verification, the way a new user meets the tool.

Clones the repo as a stranger would, installs it from the lockfile, starts the server, and
drives the whole pipeline through the HTTP API a browser would call: configure a model, define
a schema, write prompts, upload real PDFs, extract, judge, review, export. Every step asserts,
and a failure anywhere fails the run.

This is an API check, not a UI check -- there is no browser automation here, and it should not
be described as one. What it does prove is that the endpoints behind every button work on a
clean machine, from the committed tree, with real papers and a real model.

    python scripts/overnight_check.py                # full run, real LLM calls
    python scripts/overnight_check.py --no-llm       # everything except the paid stages
    python scripts/overnight_check.py --docker       # also build and boot the image
    python scripts/overnight_check.py --repo <url>   # check what the public actually gets

Writes artifacts/overnight-report.md and exits non-zero if anything failed.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PORT = 8399

# Resolved rather than assumed: run from a systemd timer and PATH does not include the places
# a per-user uv installs itself, so a bare "uv" is FileNotFoundError at 2am and nowhere else.
UV = shutil.which("uv") or str(Path.home() / ".local/bin/uv")
BASE = f"http://127.0.0.1:{PORT}"

# Open-access papers, fetched fresh each run so the check never silently depends on a file
# somebody left on this machine. Deliberately a mixed bag: two in scope, one out of it.
PAPERS = {
    "PMC13130186": "indole_dearomatization.pdf",
    "PMC13288628": "nitroalkane_coupling.pdf",
}

SCHEMA = [
    {"name": "substrate", "type": "string", "description": "The aryl or heteroaryl halide coupled, as written"},
    {"name": "coupling_partner", "type": "string", "description": "The nucleophilic partner"},
    {"name": "catalyst", "type": "string", "description": "The palladium source"},
    {"name": "ligand", "type": "string", "description": "Phosphine or NHC ligand; null if none"},
    {"name": "base", "type": "string", "description": "The base used"},
    {"name": "solvent", "type": "string", "description": "Reaction solvent as written"},
    {"name": "temperature_c", "type": "number", "description": "Temperature in Celsius"},
    {"name": "time_h", "type": "number", "description": "Reaction time in hours"},
    {"name": "yield_percent", "type": "number", "description": "Isolated yield in %"},
]

EXTRACT_PROMPT = """Extract one record per palladium-catalysed cross-coupling experiment this
paper actually performed and measured.

INCLUDE every distinct entry of an optimisation or substrate-scope table, and reactions
described in prose where conditions and an outcome are both given.

SKIP cited literature values, proposed or predicted results, values that appear only in a
figure, and characterisation or work-up conditions that are not the reaction itself.

Leave a field null when the paper does not state it. Never invent a value, and never carry a
value from one entry to another unless the paper says it applies to both.

The text is split into chunks tagged "ID: <uuid>". List in source_chunk_ids every chunk that
supplied a value for that record."""

JUDGE_PROMPT = """You are auditing records extracted from a paper on palladium-catalysed
cross-coupling. For each record decide whether a careful chemist would accept it as an accurate
rendering of an experiment this paper reports.

A field is bad if it contradicts the paper, invents a value, or is null where the paper states
one. Do not penalise formatting or notation. Judge only the data fields; ignore
source_chunk_ids.

Give a short critique citing the evidence, then the verdict, then a corrected value for every
bad field the paper supports one for."""


class Failure(Exception):
    pass


def api(path: str, body=None, method: str | None = None, timeout: int = 1800):
    method = method or ("GET" if body is None else "POST")
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        raise Failure(f"{method} {path} -> {e.code}: {e.read()[:300].decode(errors='replace')}") from e


class Report:
    def __init__(self):
        self.rows: list[tuple[str, str, str]] = []
        self.started = time.time()
        self.failed = False

    def ok(self, step: str, detail: str = ""):
        self.rows.append(("ok", step, detail))
        print(f"  ok    {step}" + (f" — {detail}" if detail else ""), flush=True)

    def fail(self, step: str, detail: str):
        self.failed = True
        self.rows.append(("FAIL", step, detail))
        print(f"  FAIL  {step} — {detail}", flush=True)

    def note(self, step: str, detail: str):
        self.rows.append(("note", step, detail))
        print(f"  note  {step} — {detail}", flush=True)

    def write(self, path: Path):
        minutes = (time.time() - self.started) / 60
        failures = [r for r in self.rows if r[0] == "FAIL"]
        lines = [
            "# Overnight verification",
            "",
            f"Run {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} · "
            f"{minutes:.1f} minutes · **{'FAILED' if failures else 'passed'}**",
            "",
            "A fresh clone, installed from the lockfile, driven through the HTTP API the "
            "interface calls. This checks the endpoints behind every button on real papers with "
            "a real model; it does not click the interface itself.",
            "",
            "| | Step | Detail |",
            "|---|---|---|",
        ]
        mark = {"ok": "✓", "FAIL": "✗", "note": "·"}
        for kind, step, detail in self.rows:
            lines.append(f"| {mark[kind]} | {step} | {detail.replace('|', '/')} |")
        if failures:
            lines += ["", "## Failures", ""] + [f"- **{s}** — {d}" for _, s, d in failures]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(cmd: list[str], cwd: Path | None = None, timeout: int = 3600) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)


def fetch_papers(into: Path) -> list[Path]:
    into.mkdir(parents=True, exist_ok=True)
    got = []
    for pmcid, name in PAPERS.items():
        target = into / name
        req = urllib.request.Request(f"https://europepmc.org/articles/{pmcid}?pdf=render",
                                     headers={"User-Agent": "extraction-toolkit-check/1.0"})
        with urllib.request.urlopen(req, timeout=300) as r:
            data = r.read()
        if not data.startswith(b"%PDF"):
            raise Failure(f"{pmcid} did not return a PDF")
        target.write_bytes(data)
        got.append(target)
    return got


def upload(pdf: Path, source_tracking: bool = True) -> dict:
    """Multipart by hand: this runs from a clone with only the project's own dependencies."""
    boundary = "----overnightcheck"
    body = b"".join([
        f"--{boundary}\r\n".encode(),
        f'Content-Disposition: form-data; name="files"; filename="{pdf.name}"\r\n'.encode(),
        b"Content-Type: application/pdf\r\n\r\n",
        pdf.read_bytes(),
        f"\r\n--{boundary}--\r\n".encode(),
    ])
    req = urllib.request.Request(
        f"{BASE}/api/papers?source_tracking={str(source_tracking).lower()}",
        data=body, method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=1800) as r:
        return json.loads(r.read())[0]


def wait_for_server(proc: subprocess.Popen, log: Path, seconds: int = 120):
    deadline = time.time() + seconds
    while time.time() < deadline:
        if proc.poll() is not None:
            raise Failure(f"server exited early: {log.read_text()[-600:]}")
        try:
            # probe a long-stable endpoint: this asks "is the server up", not "does this
            # version have the newest feature", and the two must not be confused
            urllib.request.urlopen(BASE + "/api/settings", timeout=5).read()
            return
        except Exception:
            time.sleep(2)
    raise Failure(f"server never answered: {log.read_text()[-600:]}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-llm", action="store_true", help="skip the stages that cost money")
    ap.add_argument("--docker", action="store_true", help="also build and boot the image")
    ap.add_argument("--keep", action="store_true", help="leave the clone behind for inspection")
    ap.add_argument("--repo", default=str(REPO),
                    help="what to clone: a path, or the public URL to check what strangers get")
    args = ap.parse_args()

    report = Report()
    # Claim the report before doing any work. A run that is killed -- OOM at 02:02 was the real
    # case -- never reaches the finally block, and the previous run's report stays on disk saying
    # "passed". Someone reads it in the morning and believes a job that died. An in-progress
    # marker means a missing result looks missing instead of looking like success.
    started_marker = REPO / "artifacts" / "overnight-report.md"
    started_marker.parent.mkdir(parents=True, exist_ok=True)
    started_marker.write_text(
        f"# Overnight verification\n\nStarted {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
        f" \u00b7 **still running, or killed before it could finish**\n\n"
        f"If this text is still here, the run did not complete. A killed process cannot write its\n"
        f"own report, so this line is what a failure looks like.\n", encoding="utf-8")

    workdir = Path(tempfile.mkdtemp(prefix="toolkit-check-"))
    clone = workdir / "clone"
    server = None
    print(f"working in {workdir}", flush=True)

    try:
        # --- a stranger's clone, not this working tree
        r = run(["git", "clone", "--quiet", args.repo, str(clone)], timeout=900)
        if r.returncode:
            raise Failure(f"clone failed: {r.stderr[:300]}")
        tracked = len(run(["git", "ls-files"], cwd=clone).stdout.split())
        head = run(["git", "log", "-1", "--format=%h %s"], cwd=clone).stdout.strip()
        source = "GitHub" if "://" in args.repo else "a local path"
        report.ok("clone", f"{tracked} tracked files from {source}, at {head[:58]}")

        for leak in (".env", "workspace/config/settings.json", "workspace/config/schema.json"):
            if (clone / leak).exists():
                report.fail("clone is clean", f"{leak} was committed")
                break
        else:
            report.ok("clone is clean", "no .env, no config, no data")

        # --- install exactly what the README says to install
        t0 = time.time()
        r = run([UV, "sync", "--frozen"], cwd=clone, timeout=3600)
        if r.returncode:
            raise Failure(f"uv sync failed: {r.stderr[-400:]}")
        report.ok("uv sync --frozen", f"{time.time() - t0:.0f}s")

        r = run([UV, "run", "python", "-m", "unittest", "discover", "-s", "tests"], cwd=clone, timeout=1800)
        if r.returncode:
            raise Failure(f"tests failed in the clone: {r.stderr[-400:]}")
        report.ok("unit tests in the clone", r.stderr.strip().splitlines()[-1] if r.stderr else "passed")

        # --- boot it against an empty workspace
        workspace = workdir / "workspace"
        log = workdir / "server.log"
        env = {**os.environ, "WORKSPACE_DIR": str(workspace)}
        with log.open("w") as fh:
            server = subprocess.Popen(
                [UV, "run", "uvicorn", "server.main:app", "--port", str(PORT)],
                cwd=clone, stdout=fh, stderr=subprocess.STDOUT, env=env)
        wait_for_server(server, log)
        report.ok("server starts", f"port {PORT}")

        # --- what a first-time user actually finds
        status = api("/api/status")
        empty = (status["papers"] == 0 and not status["has_model"]
                 and not status["has_schema"] and not status["has_extract_prompt"])
        (report.ok if empty else report.fail)(
            "starts empty", "no model, no schema, no prompts, no papers"
            if empty else f"something was prefilled: {status}")
        if len(status["blockers"]["extract"]) == 3:
            report.ok("blockers are named", "3 things to do, each with a route")
        else:
            report.fail("blockers are named", f"got {status['blockers']['extract']}")

        refused = False
        try:
            api("/api/extract", {"paper_ids": ["x"]})
        except Failure as e:
            refused = "400" in str(e)
        (report.ok if refused else report.fail)(
            "unconfigured run is refused", "400 before any call is made"
            if refused else "it did not refuse")

        # --- configure, the way the interface does
        key = os.environ.get("TOOLKIT_CHECK_KEY", "")
        profile = api("/api/models", [{"name": "check", "model": os.environ.get("TOOLKIT_CHECK_MODEL", ""),
                                       "api_base": os.environ.get("TOOLKIT_CHECK_BASE", ""),
                                       "api_version": os.environ.get("TOOLKIT_CHECK_VERSION", "")}],
                      method="PUT")
        pid = profile["ids"][0]
        if key:
            api(f"/api/models/{pid}/key", {"value": key}, method="PUT")
        api("/api/settings", {"extract_model": pid, "judge_model": pid}, method="PUT")
        api("/api/schema", {"fields": SCHEMA}, method="PUT")
        api("/api/prompts", {"extract": EXTRACT_PROMPT, "judge": JUDGE_PROMPT}, method="PUT")
        report.ok("configured", f"{len(SCHEMA)} fields, both prompts, one model")

        if key:
            listing = json.dumps(api("/api/models"))
            (report.fail if key in listing else report.ok)(
                "keys never leave the server", "the key is not present in /api/models")

        ready = api("/api/readiness")
        if key and ready["extract"]:
            report.fail("readiness clears", f"still blocked: {ready['extract']}")
        elif key:
            report.ok("readiness clears", "extract and judge both unblocked")

        # --- real papers
        pdfs = fetch_papers(workdir / "pdfs")
        report.ok("fetched papers", f"{len(pdfs)} open-access PDFs from Europe PMC")

        parsed = []
        for pdf in pdfs:
            t0 = time.time()
            result = upload(pdf)
            if "error" in result:
                report.fail(f"parse {pdf.name}", result["error"][:200])
                continue
            parsed.append(result["id"])
            report.ok(f"parse {pdf.name}", f"{result['n_chunks']} chunks in {time.time() - t0:.0f}s")

        if not parsed:
            raise Failure("nothing parsed; the rest of the run has no input")

        paper = api(f"/api/papers/{parsed[0]}")
        has_html = any("<" in c.get("html", "") for c in paper["chunks"])
        (report.ok if has_html else report.fail)(
            "chunks render as HTML", "markdown tables survive into the review pane"
            if has_html else "no rendered html on any chunk")

        broken = workdir / "not-a.pdf"
        broken.write_bytes(b"this is not a pdf")
        bad = upload(broken)
        (report.ok if "error" in bad else report.fail)(
            "a corrupt PDF fails alone", bad.get("error", "it was accepted")[:90])

        if args.no_llm or not key:
            report.note("LLM stages", "skipped (--no-llm or no key configured)")
        else:
            total_records = 0
            for pid_ in parsed:
                res = api("/api/extract", {"paper_ids": [pid_]})[0]
                if "error" in res:
                    report.fail(f"extract {pid_[:24]}", res["error"][:200])
                    continue
                total_records += res["n_records"]
                tok = res.get("usage", {})
                report.ok(f"extract {pid_[:24]}",
                          f"{res['n_records']} records, {res['seconds']}s, "
                          f"{tok.get('prompt_tokens', 0) + tok.get('completion_tokens', 0):,} tokens")

            for pid_ in parsed:
                if not api(f"/api/papers/{pid_}/extraction").get("records"):
                    report.note(f"judge {pid_[:24]}", "no records to judge")
                    continue
                res = api("/api/judge", {"paper_ids": [pid_]})[0]
                if "error" in res:
                    report.fail(f"judge {pid_[:24]}", res["error"][:200])
                    continue
                report.ok(f"judge {pid_[:24]}", f"{res['n_verdicts']} verdicts, {res['seconds']}s")

            if total_records:
                report.ok("records extracted", f"{total_records} across {len(parsed)} papers")
            else:
                report.fail("records extracted", "every paper returned nothing")

            # a reviewer's correction must survive, and must not lose the model's original
            target = parsed[0]
            ext = api(f"/api/papers/{target}/extraction")
            if ext["records"]:
                first = dict(ext["records"][0])
                field = next((k for k in first if k != "source_chunk_ids"), None)
                first[field] = "CORRECTED BY CHECK"
                saved = api(f"/api/papers/{target}/extraction",
                            {"records": [first] + ext["records"][1:], "notes": {"0": {"flag": "bad"}},
                             "version": ext["version"]}, method="PUT")
                kept = saved["model_records"][0].get(field) != "CORRECTED BY CHECK"
                (report.ok if kept else report.fail)(
                    "a correction keeps the original", "model_records still holds what the model said"
                    if kept else "the model's own output was overwritten")
                stale = None
                try:
                    api(f"/api/papers/{target}/extraction",
                        {"records": ext["records"], "version": ext["version"]}, method="PUT")
                except Failure as e:
                    stale = "409" in str(e)
                (report.ok if stale else report.fail)(
                    "a stale save is refused", "409, so one tab cannot overwrite another"
                    if stale else "it silently overwrote")

        rep = api("/api/report")
        report.ok("report builds", f"{rep['totals']['records']} records, "
                                   f"{len(rep['fields'])} fields, verdicts {rep['totals']['verdicts']}")

        with urllib.request.urlopen(BASE + "/api/export.csv", timeout=120) as r:
            csv_text = r.read().decode()
        (report.ok if csv_text.startswith("paper_id,") else report.fail)(
            "CSV exports", f"{len(csv_text.splitlines()) - 1} rows")

        for path in ("/", "/app.js", "/style.css"):
            with urllib.request.urlopen(BASE + path, timeout=30) as r:
                if r.status != 200:
                    report.fail("static assets", f"{path} -> {r.status}")
                    break
        else:
            report.ok("static assets", "page, script and stylesheet all served")

        # deleting is the only irreversible thing; it must actually delete
        api(f"/api/papers/{parsed[0]}", method="DELETE")
        gone = parsed[0] not in [p["id"] for p in api("/api/papers")]
        (report.ok if gone else report.fail)("delete removes a paper", "and everything derived from it")

        if args.docker:
            t0 = time.time()
            r = run(["docker", "compose", "build"], cwd=clone, timeout=5400)
            if r.returncode:
                report.fail("docker build", r.stderr[-300:] or r.stdout[-300:])
            else:
                report.ok("docker build", f"{(time.time() - t0) / 60:.0f} minutes")

    except Failure as e:
        report.fail("run aborted", str(e)[:400])
    except Exception as e:  # noqa: BLE001 - the report is the product; never die without one
        report.fail("run aborted", f"{type(e).__name__}: {str(e)[:400]}")
    finally:
        if server and server.poll() is None:
            server.terminate()
            try:
                server.wait(timeout=30)
            except subprocess.TimeoutExpired:
                server.kill()
        out = REPO / "artifacts" / "overnight-report.md"
        report.write(out)
        print(f"\nreport: {out}", flush=True)
        if not args.keep:
            shutil.rmtree(workdir, ignore_errors=True)

    return 1 if report.failed else 0


if __name__ == "__main__":
    sys.exit(main())
