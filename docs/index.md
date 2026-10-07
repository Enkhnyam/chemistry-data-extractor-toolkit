# file2records

file2records builds a dataset from a folder of scientific papers. You say which fields a
record has. A language model reads each paper and fills them in, a second model checks every
record against the paper, and you review the result with the source passage next to each
value.

It reads PDF, JATS XML, Elsevier XML, HTML and Word files, runs on your own machine, and
comes set up for RWTH's KI:connect models, which are free for RWTH members.

![The review screen: the paper on the left, records and the judge's reasoning on the right](img/review-hero.png)

## Install

=== "pip"

    ```bash
    pip install "file2records[pdf]"
    ```

=== "uv"

    ```bash
    uv add "file2records[pdf]"
    ```

The `[pdf]` part installs docling, which reads PDFs and needs PyTorch, a download of a few GB.
If your papers are XML, HTML or Word files, `pip install file2records` is enough and takes
about 350 MB.

## Try it

```bash
file2records serve my-first-project
```

This opens your browser on a finished example: an open-access paper on PET glycolysis that
has already been read, extracted, and checked. Open **Judge** to see each record beside the
passage it came from, and **Report** for the whole dataset. You don't need a key to look
around.

## Use it from the browser, the command line, or Python

=== "Browser"

    ```bash
    file2records serve my-review
    ```

    Add papers, define the fields and the prompt, and press **Extract**. Each page lists what
    it still needs before it can run.

=== "Command line"

    ```console
    $ file2records add my-review papers/
    Reading into my-review
      ✓ PMC12587479.xml  [jats]  64 chunks  doi:10.1039/d5ra05618g
      ✓ PMC13589335.xml  [jats]  84 chunks  doi:10.1186/s12880-026-02772-8
      ✓ PMC8877978.xml  [jats]  46 chunks  doi:10.3390/polym14040656
    3 added, 0 failed

    $ file2records extract my-review --only "glycoly[sz]is"
    $ file2records export my-review dataset.csv
    ```

=== "Python"

    ```python
    import file2records as fr

    project = fr.Project("my-review")
    project.add("papers/")
    project.extract(only=r"glycoly[sz]is")
    project.export("dataset.csv")
    ```

All three work on the same project folder. You can run the extraction from a script and
review it in the browser afterwards.

The command line and Python find your model through two lines in a `.env` file. You don't
need a model name:

```bash title=".env"
FILE2RECORDS_API_KEY=your-key
FILE2RECORDS_ENDPOINT=https://chat.kiconnect.nrw/api/v1
```

The endpoint line is for services such as RWTH KI:connect. Keys from OpenAI, Anthropic,
Gemini, Groq and xAI don't need it. See [Connect your model](how-to/connect.md).

## Next steps

The [tutorial](tutorial.md) builds a small PET glycolysis dataset from three real papers and
takes about 15 minutes. After that, the how-to guides cover single tasks. Start with
[Connect your model](how-to/connect.md), then [Add papers in any format](how-to/add-papers.md).
