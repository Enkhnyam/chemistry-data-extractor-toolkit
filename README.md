# file2records

file2records builds a dataset from a folder of scientific papers. You say which fields a
record has. A language model reads each paper and fills them in, a second model checks every
record against the paper, and you review the result with the source passage next to each
value. It reads PDF, JATS XML, Elsevier XML, HTML, and Word files, runs on your own machine,
and comes set up for RWTH's free KI:connect models.

Documentation: <https://enkhnyam.github.io/chemistry-data-extractor-toolkit/>

```bash
pip install "file2records[pdf]"        # or: pip install file2records   (no PDFs, ~250 MB)
file2records serve my-first-project    # opens a finished example in your browser
```

```python
import file2records as fr

project = fr.Project("my-review")
project.add("papers/")                                   # PDF, XML, HTML, Word, Markdown
project.extract(model=fr.rwth(), only=r"glycoly[sz]is")  # RWTH_API_KEY from the environment
project.judge(model=fr.rwth())
project.export("dataset.csv")                            # one row per record, with its DOI
```

Start with the [tutorial](https://enkhnyam.github.io/chemistry-data-extractor-toolkit/tutorial/):
a PET glycolysis dataset from three real papers in 15 minutes.

## Development

```bash
uv sync                                       # includes docling for PDF tests
uv run python -m unittest discover -s tests   # no network, no key
uvx zensical serve                            # the docs, at http://localhost:8000
```

Releasing: [RELEASING.md](RELEASING.md). Licence: the code is MIT; the demo paper is CC BY
([NOTICE](src/file2records/demo/NOTICE.md)). Please cite: [CITATION.cff](CITATION.cff).
