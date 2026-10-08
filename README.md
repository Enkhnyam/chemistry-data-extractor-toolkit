# file2records

file2records builds a dataset from a folder of scientific papers. You say which fields a
record has. A language model reads each paper and fills them in, a second pass checks every
record against the paper, and you review the result with the source passage next to each
value.

![How file2records works: parse, extract, judge, review](https://raw.githubusercontent.com/Enkhnyam/chemistry-data-extractor-toolkit/main/docs/img/pipeline.png)

It reads PDF, JATS XML, Elsevier XML, HTML, and Word files, and works with any
OpenAI-compatible AI service, such as your university's. Everything stays on your computer
except the paper text, which goes to that service, and, if you turn on identifiers, the
chemical names looked up in EBI's [Ontology Lookup Service](https://www.ebi.ac.uk/ols4/).

**Documentation: <https://enkhnyam.github.io/chemistry-data-extractor-toolkit/>**

## Install

```bash
pip install file2records            # reads PDF, XML, HTML, Word, Markdown (2–6 GB, with PyTorch)
```

## Try it

```bash
file2records serve                  # a finished example in your browser, no key needed
file2records serve my-project       # your own project
```

## Use it from Python

```python
from pathlib import Path
import file2records as fr

project = fr.Project("my-project")
project.add("papers")                    # PDF, XML, HTML, Word, Markdown

project.schema = {                       # the columns of your dataset
    "catalyst": ("string", "Catalyst as the paper names it"),
    "temperature_c": ("number", "Reaction temperature in °C"),
}
project.prompt = Path("prompt.txt")      # what counts as one record
project.identifiers = {"catalyst": "chebi"}   # optional: ChEBI IDs next to chemical names

project.extract(only=r"hydrogenation")   # only papers whose text matches
project.judge()                          # a second pass checks every record
project.export("dataset.csv")            # one row per record, with its DOI
```

The model comes from a `.env` file with three values from your AI service:

```bash
FILE2RECORDS_ENDPOINT=https://chat.kiconnect.nrw/api/v1    # RWTH KI:connect, as an example
FILE2RECORDS_API_KEY=your-key
FILE2RECORDS_MODEL=gpt-oss-120b
```

[Get started](https://enkhnyam.github.io/chemistry-data-extractor-toolkit/get-started/) walks
through the whole pipeline once, in the browser and in Python, with three real papers.

## Development

```bash
uv sync                                       # installs the package and its dependencies
uv run python -m unittest discover -s tests   # no network, no key
uvx zensical serve                            # the docs, at http://localhost:8000
```

To release, set the version in `pyproject.toml`, `src/file2records/__init__.py` and
`CITATION.cff`, then push a tag such as `v0.3.0`. GitHub Actions then publishes it to PyPI.

Licence: the code is MIT; the demo paper is CC BY 3.0
([NOTICE](https://github.com/Enkhnyam/chemistry-data-extractor-toolkit/blob/main/src/file2records/demo/NOTICE.md)).
To cite file2records, use [CITATION.cff](https://github.com/Enkhnyam/chemistry-data-extractor-toolkit/blob/main/CITATION.cff).
