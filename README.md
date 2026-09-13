# Extraction Toolkit

Turn a folder of PDFs into structured, LLM-extracted, LLM-audited records &mdash; on your
own machine, in whatever schema your field needs. Built out of the pipeline behind the
[pet-depolymerisation-database](../pet-depolymerisation-database) project, generalised: the
schema, the extraction prompt, the judge rubric and the few-shot examples are all yours to
edit from the app, nothing is hardcoded to one chemistry.

Three stages, one page each:

1. **Parse** &mdash; upload PDFs. Parsed with [docling](https://github.com/docling-project/docling)
   into text/table chunks; source tracking (on by default) tags every chunk with a stable id
   so extracted records can cite exactly where a value came from.
2. **Extract** &mdash; an LLM call per paper turns its parsed text into records matching your
   schema, using your prompt and optional worked examples. Both are edited from the Extract page
   itself, beside the run button, so what a run will use is visible at the moment you start it.
3. **Judge** &mdash; a second LLM call per paper audits those records against the paper's own
   text: a verdict, a critique, and field-level fixes per record.

Every stage's review page shows the paper's full text (markdown-rendered, so tables read as
tables) next to its records:

- click a **record** to shade the chunks it cites
- click a **field** to mark every occurrence of its value in the text; click again to walk to
  the next one
- **edit** any record, or apply one of the judge's proposed fixes, and flag/annotate it — your
  corrections are written to disk beside the model's original output, which is kept under
  `model_records` so the two can always be diffed

Runs happen one paper at a time with live per-item progress, a time estimate drawn from your
own machine's history, and a running token and dollar count. You can switch tabs while a run
is going, and stop it after the current paper. What each paper has cost is listed per row on
the Parse and Report tables, with a total; a run can be deleted and re-run from either page,
behind a confirmation that names what goes with it.

A fourth page, **Report**, summarises whatever you have built: completeness by field, records
per paper, what the judge changed, the distribution of any field you pick, and CSV/JSON export
of every record with its verdict and your notes. It reads the loaded schema, so it describes a
metal-salt corpus as readily as an ionic-liquid one.

Everything is stored as plain JSON/PDF files under `workspace/` (or wherever `WORKSPACE_DIR`
points) &mdash; no database. The only things that leave your machine are the calls to whichever
LLM provider you configure, and a one-time OCR model download the first time you parse.

## Before you start

- **The install is large.** docling brings PyTorch: expect roughly **6 GB** on disk and several
  minutes for the first `uv sync`.
- **The first PDF you parse downloads OCR models** (~60 MB, from ModelScope). After that
  parsing is fully offline. Everything else already is, apart from calls to whichever LLM
  provider you configure.
- **There is no authentication.** The API can read and write this machine's provider keys and
  spend money against them, so it must stay bound to localhost unless you put an
  authenticating proxy in front of it.

## Run it

### With uv (fastest for local development)

```bash
uv sync
cp .env.example .env   # then fill in your provider's key, or set it later from Settings
uv run uvicorn server.main:app --reload
```

Open http://localhost:8000.

### With Docker

```bash
cp .env.example .env   # fill in your provider's key -- the UI's key-save writes inside the
                        # container and won't survive a rebuild, so set it here for Docker use
docker compose up --build
```

Data persists in `./data` on the host (mounted to `/data` in the container). The port is bound
to `127.0.0.1` deliberately: the API can read this machine's provider keys and has no
authentication, so it must not be published to a network.

**The build needs memory.** It installs PyTorch (CPU-only wheels — the Dockerfile pins the
CPU index, which avoids about 1.5 GB of unusable CUDA packages). Unpacking it inside Docker's
VM wants roughly 6-8 GB of headroom; on a machine already using most of its RAM the build
stalls or the VM is OOM-killed. If that happens, close what you can, give Docker's VM at least
8 GB, and build once — or just use the `uv` path above, which has no VM in the way.

## Nothing is filled in for you

A fresh install has **no model, no schema and no prompts** &mdash; it writes no config files at
all until you save something. Each empty field instead shows a real example from a PET
depolymerisation corpus as **grey placeholder text**: the ten-field schema, the extraction
prompt, the rubric. None of it is ever a value; "Use the example" copies it in if you want it.

This is deliberate. Those examples used to be defaults, which meant a first run quietly
extracted ionic-liquid chemistry from whatever you uploaded and looked like it had worked.

Extract and Judge show a readiness checklist beside the run button &mdash; model, key, schema,
prompt &mdash; and the run is refused, by the server as well as the button, until every row is
green.

A **worked example** is one paper's text paired with the records it should produce. The editor
lays it out in the order the model sees it &mdash; prompt, then paper text, then records &mdash;
with the JSON brackets pre-filled, a placeholder built from your own schema, and live validation
against it.

## Configuring for your own domain

Everything that makes this specific to ionic-liquid PET depolymerisation lives in
`workspace/config/` and is editable from the **Settings** page, not in code:

- `schema.json` &mdash; the fields a record has (name, type, description)
- `extract_prompt.txt` &mdash; the extraction instructions
- `judge_prompt.txt` &mdash; the judge's rubric
- `few_shot.json` &mdash; optional worked examples, `[{"text": ..., "records": [...]}]`

None of these exist until you save them; the examples shown in the interface live in
`server/exemplar.py` and are only ever placeholder text.

Change all four and the same three-stage pipeline runs on a different literature entirely.

## Models

You configure one entry per endpoint you call: a name, a
[litellm](https://docs.litellm.ai/docs/providers) model string, a key, and an endpoint and API
version where the provider needs them (Azure does; most do not). **Extraction and judging then
pick separately** &mdash; a strong extractor and a cheaper or deliberately different auditor, each
with its own endpoint and key, in one workspace.

Credentials are passed per call rather than left to provider environment variables, so an Azure
deployment and an OpenAI model can coexist without fighting over one `OPENAI_API_KEY`. Each
entry's key is written to this project's local `.env` under its own variable and is never sent
back to the browser. "Test connection" makes one tiny call against that exact configuration.

## API

| Method | Path | Purpose |
|---|---|---|
| GET/PUT | `/api/settings` | model string, default source-tracking |
| GET/PUT | `/api/schema` | record fields |
| GET/PUT | `/api/prompts` | extraction prompt, judge rubric |
| GET/PUT | `/api/few-shot` | few-shot examples |
| GET/PUT | `/api/models` | the configured endpoints, and which stage uses which |
| PUT | `/api/models/{id}/key` | set one entry's key |
| POST | `/api/models/{id}/test` | one tiny completion against that exact configuration |
| GET | `/api/status` | pipeline state: counts, what is configured, what blocks a run |
| GET | `/api/readiness` | what still has to be done before each stage can run |
| GET | `/api/env-keys` | which provider env vars are set (never their values) |
| PUT | `/api/api-key` | write a variable to `.env` |
| GET | `/api/timings` | median duration per stage, from your own runs |
| POST | `/api/papers` | upload + parse PDFs (multipart, `source_tracking` query param) |
| GET | `/api/papers` | list papers and their stage status |
| GET | `/api/papers/{id}` | parsed chunks, with rendered HTML |
| POST | `/api/extract` | `{paper_ids: [...]}` &rarr; run extraction |
| GET | `/api/papers/{id}/extraction` | extracted records |
| PUT | `/api/papers/{id}/extraction` | save reviewer corrections + notes |
| POST | `/api/judge` | `{paper_ids: [...]}` &rarr; run the judge |
| GET | `/api/papers/{id}/judgment` | verdicts and fixes |
| DELETE | `/api/papers/{id}` | the paper and every stage derived from it |
| DELETE | `/api/papers/{id}/extraction` | the extraction, its judgment, and your notes |
| DELETE | `/api/papers/{id}/judgment` | the verdicts only; records stay |
| GET | `/api/api-key/{name}` | the stored value of one variable, so Settings can edit it |
| POST | `/api/generate-prompt` | draft an extraction prompt or judge rubric for a domain |
| GET | `/api/report` | corpus summary: completeness, verdicts, corrections per field |
| GET | `/api/export.csv` / `.json` | every record flattened, with verdicts and your notes |

## Where your data lives

```
workspace/
  pdfs/       the uploaded PDFs
  parsed/     one JSON per paper: chunks with stable ids
  extracted/  records, plus model_records (what the model said before you corrected it) and notes
  judged/     verdicts and proposed fixes
  config/     schema.json, extract_prompt.txt, judge_prompt.txt, few_shot.json, settings.json
```

Nothing else is written anywhere. Point `WORKSPACE_DIR` elsewhere to keep several corpora
side by side.

## Tests

```bash
uv run python -m unittest discover -s tests
```

### End-to-end check

```bash
uv run python scripts/overnight_check.py            # real papers, real model calls
uv run python scripts/overnight_check.py --no-llm   # everything except the paid stages
uv run python scripts/overnight_check.py --docker   # also build the image
```

Clones this repo the way a stranger would, installs it from the lockfile, boots the server
against an empty workspace, and drives the whole pipeline through the HTTP API: configure a
model, define a schema, write prompts, fetch and parse real open-access PDFs, extract, judge,
correct a record, export, delete. It asserts the things that have actually broken before &mdash;
that a clone carries no `.env` or config, that an unconfigured run is refused, that a key never
appears in a listing, that a correction keeps the model's original, that a stale save is
refused. Writes `artifacts/overnight-report.md` and exits non-zero on any failure.

It drives the API the interface calls; it does not click the interface. There is no browser
automation here and the report says so.

Twenty-three smoke tests over every endpoint that does not need a model: config validation,
credential checks, the review save path (including its refusal to overwrite a newer edit),
deletes, per-paper cost, the report and the exports, and that a corrupt PDF fails only its own
upload. No network, no API key, no pytest &mdash; they run against a throwaway workspace in
about a second.

## What's not in v1

One run at a time, in the server process, with no job queue &mdash; fine for the batch sizes a
systematic review actually has; a second concurrent run is refused rather than queued. No
multi-user auth: this is a single-researcher local tool. Editing a record after the judge has
run marks its verdict stale rather than re-judging it for you.
