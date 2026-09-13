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
   schema, using your prompt and optional few-shot examples.
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
is going, and stop it after the current paper.

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

Data persists in `./data` on the host (mounted to `/data` in the container).

## Configuring for your own domain

Everything that makes this specific to ionic-liquid PET depolymerisation lives in
`workspace/config/` and is editable from the **Settings** page, not in code:

- `schema.json` &mdash; the fields a record has (name, type, description)
- `extract_prompt.txt` &mdash; the extraction instructions
- `judge_prompt.txt` &mdash; the judge's rubric
- `few_shot.json` &mdash; optional worked examples, `[{"text": ..., "records": [...]}]`

Change all four and the same three-stage pipeline runs on a different literature entirely.

## Model / API keys

The model is any [litellm](https://docs.litellm.ai/docs/providers) model string
(`gpt-4o-mini`, `anthropic/claude-sonnet-4-5`, `ollama/llama3`, ...), set from Settings.
Provider API keys are read from environment variables (`OPENAI_API_KEY`,
`ANTHROPIC_API_KEY`, ...) via `.env`, or entered directly in Settings &mdash; either way they
stay on this machine.

## API

| Method | Path | Purpose |
|---|---|---|
| GET/PUT | `/api/settings` | model string, default source-tracking |
| GET/PUT | `/api/schema` | record fields |
| GET/PUT | `/api/prompts` | extraction prompt, judge rubric |
| GET/PUT | `/api/few-shot` | few-shot examples |
| GET | `/api/env-keys` | which provider env vars are set (never their values) |
| PUT | `/api/api-key` | write a provider key to `.env` |
| POST | `/api/test-model` | one tiny completion — "does my model + key work?" |
| GET | `/api/timings` | median duration per stage, from your own runs |
| POST | `/api/papers` | upload + parse PDFs (multipart, `source_tracking` query param) |
| GET | `/api/papers` | list papers and their stage status |
| GET | `/api/papers/{id}` | parsed chunks, with rendered HTML |
| POST | `/api/extract` | `{paper_ids: [...]}` &rarr; run extraction |
| GET | `/api/papers/{id}/extraction` | extracted records |
| PUT | `/api/papers/{id}/extraction` | save reviewer corrections + notes |
| POST | `/api/judge` | `{paper_ids: [...]}` &rarr; run the judge |
| GET | `/api/papers/{id}/judgment` | verdicts and fixes |
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

Thirteen smoke tests over every endpoint that does not need a model: config validation, the
review save path (including its refusal to overwrite a newer edit), the report, the exports,
and that a corrupt PDF fails only its own upload. No network, no API key, no pytest &mdash;
they run against a throwaway workspace in about a second.

## What's not in v1

One run at a time, in the server process, with no job queue &mdash; fine for the batch sizes a
systematic review actually has; a second concurrent run is refused rather than queued. No
multi-user auth: this is a single-researcher local tool. Editing a record after the judge has
run marks its verdict stale rather than re-judging it for you.
