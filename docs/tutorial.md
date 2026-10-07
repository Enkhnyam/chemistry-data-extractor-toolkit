# Tutorial: a PET glycolysis dataset

You will build a small dataset of PET glycolysis experiments — catalyst, temperature, time,
BHET yield — from three real open-access papers. It takes about 15 minutes, most of it
waiting for the model.

You need Python 3.10 or newer and an RWTH account. Everything else is free.

## 1. Install

```bash
pip install file2records
```

The papers in this tutorial are XML, so the PDF extra isn't needed.

## 2. Get an RWTH key

Log in at [chat.kiconnect.nrw](https://chat.kiconnect.nrw) with RWTH single sign-on, click your
name (bottom left) → **API Key Management** → **Create Key**. Then, in an empty folder:

```bash title=".env"
RWTH_API_KEY=paste-your-key-here
```

## 3. Download three papers

Europe PMC gives the full text of open-access papers to anyone, as XML:

```bash
mkdir papers
for id in PMC12587479 PMC8877978 PMC13589335; do
  curl -s -o papers/$id.xml "https://www.ebi.ac.uk/europepmc/webservices/rest/$id/fullTextXML"
done
```

Two are about PET glycolysis. The third, `PMC13589335`, is a cancer imaging study that a
search for "PET glycolysis" also finds — you will filter it out in step 5.

## 4. Read them into a project

```python title="tutorial.py"
import file2records as fr

project = fr.Project("pet-review")
for paper in project.add("papers"):
    print(paper["filename"], paper["format"], paper["doi"])
```

```console
$ python tutorial.py
PMC12587479.xml jats 10.1039/d5ra05618g
PMC13589335.xml jats 10.1186/s12880-026-02772-8
PMC8877978.xml jats 10.3390/polym14040656
```

Keep adding each step's code to `tutorial.py` and run it again; the outputs below show only
what the new part prints. Re-reading a paper you already added is harmless.

`pet-review/` is now a project folder. Each paper is split into chunks (paragraphs and whole
tables) so that every value extracted later can point at the chunk it came from.

## 5. Choose the papers worth a model call

Searching is free — it reads the text you already have:

```python title="tutorial.py"
for hit in project.search(r"BHET yield"):
    print(f"{hit['matches']:3} matches  {hit['title'][:60]}")

print(project.select(only=r"glycoly[sz]is", exclude=r"tumou?r|positron|tomograph"))
```

```console
 22 matches  Optimizing PET Glycolysis with an Oyster Shell-Derived Catal
 16 matches  Magnetically recoverable cobalt oxide nanoparticle catalyst
['pmc12587479-b8154390', 'pmc8877978-27725354']
```

`only` keeps papers whose text matches, `exclude` drops papers whose text matches. The cancer
paper is gone. See [Choose papers with a regex](how-to/choose-papers.md) for more patterns.

## 6. Say what a record is

A record is one experiment. Describe each field — the model reads these descriptions:

```python title="tutorial.py"
from pydantic import BaseModel, Field

class Experiment(BaseModel):
    catalyst: str | None = Field(None, description="Catalyst exactly as the paper names it")
    temperature_c: float | None = Field(None, description="Reaction temperature in °C")
    time_min: float | None = Field(None, description="Reaction time in minutes")
    bhet_yield_percent: float | None = Field(None, description="BHET yield, %")

project.schema = Experiment
project.prompt = """Extract every PET glycolysis experiment this paper reports, one record per run.
Skip values quoted from other papers. Unreported values are null."""
project.rubric = """Check each record against the paper. A record is wrong if a value does not
match the run it describes, or if it is not an experiment from this paper."""
```

Ask whether anything is missing before spending a call:

```python
print(project.check("extract", fr.rwth()))
```

```console
[]
```

An empty list means ready. If you forgot the key, you'd see instead:

```console
['No RWTH key. Set RWTH_API_KEY, or create one at https://chat.kiconnect.nrw under API Key Management.']
```

## 7. Extract and judge

```python title="tutorial.py"
from dotenv import load_dotenv
load_dotenv()                    # reads RWTH_API_KEY from .env

papers = dict(only=r"glycoly[sz]is", exclude=r"tumou?r|positron|tomograph")
project.extract(model=fr.rwth(), **papers, on_paper=print)
project.judge(model=fr.rwth(), **papers, on_paper=print)
```

Each paper prints one line as it finishes, with how many records it gave and how long it took.
Run the script again and finished papers are skipped — pass `redo=True` to run them again.

## 8. Review in the browser

```bash
file2records serve pet-review
```

Open **Judge**, pick a paper. Click a record to shade the passages it cites; the judge's
reasoning is under each record, and any value it would change is marked with an **apply**
button. Nothing changes unless you press it.

![Review: a record, the judge's reasoning, and a proposed fix](img/review.png)

## 9. Export

```python
project.export("pet_glycolysis.csv", **papers)
```

One row per record, with the paper's DOI, the judge's verdict and reasoning, and which model
produced it.

## What you did

- read three papers from XML, with their DOIs
- dropped an off-topic paper by its text, for free
- defined a record as a pydantic model and wrote a two-line prompt
- extracted and audited with a free RWTH model
- reviewed against the source and exported a citable CSV

Next: [write a better schema and prompt](how-to/schema-and-prompts.md), or point it at your
own papers with [Add papers in any format](how-to/add-papers.md).
