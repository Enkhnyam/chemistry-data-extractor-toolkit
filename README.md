# file2records

Turn a folder of papers into a structured dataset you can trust. One model reads each paper and
fills a schema you define; a second model re-reads the paper and audits every record against it;
you review what is left with the source text beside you and the passage behind each value
highlighted. Everything runs on your own machine, and the schema, prompts and examples are yours
to edit — so the same pipeline works on PET depolymerisation, palladium catalysis or anything
else without touching the code.

It reads the formats publishers actually deliver: **PDF**, **JATS XML** (PubMed Central, Europe
PMC, RSC, Springer Nature, MDPI…), **Elsevier XML** (the ScienceDirect text-mining API),
**HTML**, **Word** and **Markdown**. And it works out of the box with **RWTH's KI:connect**.

![How it works](https://raw.githubusercontent.com/Enkhnyam/chemistry-data-extractor-toolkit/main/docs/pipeline.png)

## Install

```bash
pip install "file2records[pdf]"      # everything, including PDF reading
```

`[pdf]` adds docling, the PDF reader, which brings PyTorch and its layout models — a download of
a few GB. If your papers are XML, HTML, Word or Markdown you do not need it:

```bash
pip install file2records             # every format except PDF, about 200 MB
```

On a machine without a GPU, install the CPU build of PyTorch first and save ~3 GB of GPU
libraries: `pip install torch --index-url https://download.pytorch.org/whl/cpu`.

Python 3.10 or newer.

## Use it in the browser

```bash
file2records serve my-review
```

Opens <http://localhost:8000> on the project folder `my-review` (created if it does not exist).
A new folder opens on a finished demo — an open-access PET glycolysis paper, already parsed,
extracted and judged — so you can see the output before setting anything up. **Clear the demo**
empties it for your own work.

The app shows a checklist of what it still needs and refuses to run until it has it:

1. **Add a model** — Settings → Models. **Add RWTH KI:connect** fills in RWTH's endpoint; for
   anything else give a model string (`gpt-4o-mini`, `anthropic/claude-sonnet-4-5`,
   `ollama/llama3`, `azure/your-deployment`) and its key. **List models** asks an endpoint what
   it serves; **Test connection** proves the whole thing works. Extraction and judging choose
   their model separately.
2. **Define your schema** — the fields one record has, with a description of each. The model
   reads those descriptions, so say what you mean.
3. **Write the extraction prompt** — what to pull out of each paper and what to skip. Optionally
   add a worked example: a piece of text paired with the records it should produce.
4. **Parse** — drop in files or a whole folder. Leave source tracking on and every record can
   cite the exact chunk a value came from.
5. **Search** — a regular expression over the full text of every paper, free, no model call.
   On the Extract and Judge pages the same patterns select papers: *only* papers matching
   `glycoly[sz]is`, *except* those matching `positron|tomograph`.
6. **Extract** — one call per paper, with live progress, a time estimate and a running cost.
7. **Judge** — a second model re-reads each paper and checks every record, flagging fields and
   proposing fixes.
8. **Review** — the paper on the left, its records on the right. Click a record to shade the
   chunks it cites; edit anything, or apply the judge's proposed fix.
9. **Report** — completeness by field, what the judge changed, the distribution of any field,
   and export: records as CSV or JSON, or the **full bundle** — the dataset together with the
   schema, prompts, models and a manifest. Exports can be limited by the same regex filters.

## Use it from the command line

```bash
file2records add my-review papers/                    # files or folders, any supported format
file2records papers my-review                         # what is in the project
file2records search my-review "glycoly[sz]is"         # full-text regex search, with snippets
file2records check my-review                          # what is missing before a run
file2records extract my-review --model rwth/gpt-oss-120b \
    --only "glycoly[sz]is" --exclude "positron|tomograph"
file2records judge my-review --model rwth/gpt-oss-120b
file2records export my-review dataset.csv             # .csv, .json, or .zip for the bundle
```

`extract` and `judge` skip papers already done (`--redo` to run them again). Without `--model`
they use the models chosen in the web app's Settings. The schema and prompts are the project's,
set in the web app or from Python.

## Use it from Python

```python
import file2records as fr

project = fr.Project("my-review")
project.add("papers/")
project.schema = "schema.json"            # or a list of fields, or a pydantic model
project.prompt = "prompts/extract.txt"    # text, or a file holding it
project.rubric = "prompts/judge.txt"

project.extract(model=fr.rwth(), only=r"glycoly[sz]is", exclude=r"positron|tomograph")
project.judge(model=fr.rwth())

rows = project.records()                  # one dict per record, with DOI and judge verdict
project.export("dataset.csv")
```

A schema as a pydantic model:

```python
from pydantic import BaseModel, Field

class Glycolysis(BaseModel):
    catalyst: str | None = Field(None, description="Catalyst name exactly as written")
    temperature_c: float | None = Field(None, description="Temperature in °C")
    bhet_yield_percent: float | None = Field(None, description="BHET yield, %")

project.schema = Glycolysis
```

`model` is any [litellm](https://docs.litellm.ai/docs/providers) model string, `"rwth/<name>"`,
`fr.rwth(...)`, or a dict of litellm parameters (`model`, `api_key`, `api_base`, …). A project
is the same folder the web app shows, so work started in Python can be reviewed in the browser.

## RWTH KI:connect

RWTH's [KI:connect](https://chat.kiconnect.nrw) is OpenAI-compatible, and its open models
(`gpt-oss-120b`, `mistral-small-4-119b-2603`) cost nothing to use. Log in with RWTH single
sign-on, open **API Key Management**, create a key, and either:

- in the browser: Settings → **Add RWTH KI:connect**, then paste the key, or
- on the command line / in Python: `export RWTH_API_KEY=...` and use `rwth/gpt-oss-120b`.

The endpoint allows a few requests at a time; file2records sends one at a time.

## File formats

| Format | Read with | Notes |
|---|---|---|
| PDF | docling (`[pdf]` extra) | layout and table models; scanned pages are OCR'd |
| JATS XML | built in | PMC / Europe PMC and the many publishers using JATS. Recognised without a DOCTYPE line |
| Elsevier XML | built in | the article API's FULL view; table footnotes kept with their table |
| other XML | built in, general reader | paragraphs and tables; marked "XML (general)" so you know |
| HTML | built in | a saved article page; `citation_doi` / `citation_title` meta tags are used |
| Word (.docx) | built in | headings, paragraphs, tables |
| Markdown, text | built in | |

Prefer XML or HTML to a PDF when you have both: their tables arrive as rows and cells rather
than as whatever a layout model recovers from a picture of them. Every paper records the DOI and
title it states, and every exported record carries its paper's DOI.

## Your data, and other people's

- Everything is plain JSON and the original files in the project folder — no database. The only
  things that leave the machine are calls to your model provider, and a one-time model download
  on the first PDF.
- API keys are written to `.env` in the project folder and never sent back to the browser.
- **The bundle does not contain paper text unless you ask for it.** Papers obtained under a
  publisher's text-and-data-mining agreement may be mined, not redistributed. Records keep their
  DOI and the ids of the chunks they cite, which is enough for anyone with access to the paper to
  check them. Tick *include paper text* (or `--include-text`) only for open-access papers.
- Nothing is applied automatically. The judge is a tireless second reader, not an authority — in
  our own validation, 21 of 22 proposals to rename a substance turned out to be two acceptable
  names for the same compound rather than errors.
- There is no login, so `serve` listens on localhost only. Keep it that way.

The demo paper is CC BY and redistributed with attribution; see
[`src/file2records/demo/NOTICE.md`](src/file2records/demo/NOTICE.md). Everything else is MIT.

## Docker

```bash
docker compose up --build
```

Same address. The project folder is `./data/`, kept between runs.

## Development

```bash
git clone https://github.com/Enkhnyam/chemistry-data-extractor-toolkit.git
cd chemistry-data-extractor-toolkit
uv sync                                          # includes docling for PDF tests
uv run python -m unittest discover -s tests     # no network, no key
uv run file2records serve
```

Releasing: see [RELEASING.md](RELEASING.md).

## Licence

MIT — see [LICENSE](LICENSE). If you use it in published work, please cite it; see
[CITATION.cff](CITATION.cff).
