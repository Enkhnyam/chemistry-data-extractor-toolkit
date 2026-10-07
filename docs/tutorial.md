# Tutorial: a PET glycolysis dataset

In this tutorial you build a small dataset of PET glycolysis experiments from three
open-access papers. Each record has a catalyst, a temperature, a reaction time, and a BHET
yield. It takes about 15 minutes, and most of that is waiting for the model.

You need Python 3.10 or later and an RWTH account.

## 1. Install file2records

```bash
pip install file2records
```

The papers in this tutorial are XML files, so you don't need the PDF extra.

## 2. Get an RWTH key

Log in at [chat.kiconnect.nrw](https://chat.kiconnect.nrw) with your RWTH account. Click
your name in the bottom-left corner, then **API Key Management**, then **Create Key**.

Make an empty folder for the tutorial and save the key in a file called `.env`:

```bash title=".env"
RWTH_API_KEY=paste-your-key-here
```

## 3. Download three papers

Europe PMC publishes the full text of open-access papers as XML, and you don't need an
account to download it:

```bash
mkdir papers
for id in PMC12587479 PMC8877978 PMC13589335; do
  curl -s -o papers/$id.xml "https://www.ebi.ac.uk/europepmc/webservices/rest/$id/fullTextXML"
done
```

Two of these papers are about PET glycolysis. The third, `PMC13589335`, is a cancer imaging
study. A search for "PET glycolysis" finds papers like it too, and step 5 shows how to leave
them out.

## 4. Read the papers into a project

Create `tutorial.py`:

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

file2records created the folder `pet-review/` and split each paper into chunks: one per
paragraph, and one per table. Later, every extracted value records which chunk it came from.

In the next steps you add code to the end of `tutorial.py` and run it again. The output shown
is only what the new code prints. Adding a paper that's already in the project does nothing.

## 5. Choose the papers to send to the model

Searching the text you already have costs nothing:

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

`select` keeps the papers whose text matches `only` and then removes the ones that match
`exclude`. The cancer study isn't in the list. For more patterns, see
[Choose papers with a regex](how-to/choose-papers.md).

## 6. Define a record

A record is one experiment. Describe each field in plain words, because the model reads these
descriptions:

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

Before you use the model, check that nothing is missing:

```python
print(project.check("extract", fr.rwth()))
```

```console
[]
```

An empty list means the project is ready. Without a key, the list says so:

```console
['No RWTH key. Set RWTH_API_KEY, or create one at https://chat.kiconnect.nrw under API Key Management.']
```

## 7. Extract and check the records

```python title="tutorial.py"
from dotenv import load_dotenv
load_dotenv()                    # reads RWTH_API_KEY from .env

papers = dict(only=r"glycoly[sz]is", exclude=r"tumou?r|positron|tomograph")
project.extract(model=fr.rwth(), **papers, on_paper=print)
project.judge(model=fr.rwth(), **papers, on_paper=print)
```

As each paper finishes, the script prints how many records it produced and how long it took.
If you run the script again, papers that are done are skipped. To run them again, pass
`redo=True`.

## 8. Review the records

```bash
file2records serve pet-review
```

Open **Judge** and choose a paper. When you click a record, the passages it cites are
highlighted. Under each record is the judge's reasoning. If the judge thinks a value is
wrong, the field shows its suggestion and an **apply** button. Values only change when you
press it.

![A record, the judge's reasoning, and a suggested correction](img/review.png)

## 9. Export the dataset

```python
project.export("pet_glycolysis.csv", **papers)
```

The CSV file has one row per record. Each row includes the paper's DOI, the judge's verdict
and reasoning, and the model that produced it.

## Next steps

You now have a dataset you can check against its sources. The guide to [writing the schema and prompts](how-to/schema-and-prompts.md) shows how to
improve it, and the guide to [adding papers](how-to/add-papers.md) shows how to use your own.
