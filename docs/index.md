# file2records

**Turn a folder of papers into a dataset you can check.** One model reads each paper and fills
the fields you define. A second model re-reads the paper and audits every record. You review
what is left with the source passage beside each value.

It reads what publishers actually give you — PDF, JATS XML, Elsevier XML, HTML, Word — runs on
your machine, and works out of the box with RWTH's free KI:connect models.

![The review screen: paper on the left, records and the judge's reasoning on the right](img/review-hero.png)

## Install

=== "pip"

    ```bash
    pip install "file2records[pdf]"
    ```

=== "uv"

    ```bash
    uv add "file2records[pdf]"
    ```

!!! tip "No PDFs? Skip the big download"
    `[pdf]` adds the PDF reader, which brings PyTorch (a few GB). For XML, HTML, Word and
    Markdown, `pip install file2records` is enough — about 250 MB.

## See it work in one minute

```bash
file2records serve my-first-project
```

Your browser opens on a finished example: an open-access PET glycolysis paper, already read,
extracted and judged. Click **Judge** to see each record next to the passage it came from, and
**Report** for the whole dataset. No key needed to look.

## Three ways to use it

=== "Browser"

    ```bash
    file2records serve my-review
    ```

    Drop in papers, set the fields and the prompt, press Extract, review, export. Every step
    has a checklist that says what is still missing.

=== "Command line"

    ```console
    $ file2records add my-review papers/
    Reading into my-review
      ✓ PMC12587479.xml  [jats]  64 chunks  doi:10.1039/d5ra05618g
      ✓ PMC13589335.xml  [jats]  84 chunks  doi:10.1186/s12880-026-02772-8
      ✓ PMC8877978.xml  [jats]  46 chunks  doi:10.3390/polym14040656
    3 added, 0 failed

    $ file2records extract my-review --model rwth/gpt-oss-120b --only "glycoly[sz]is"
    $ file2records export my-review dataset.csv
    ```

=== "Python"

    ```python
    import file2records as fr

    project = fr.Project("my-review")
    project.add("papers/")
    project.extract(model=fr.rwth(), only=r"glycoly[sz]is")
    project.export("dataset.csv")
    ```

All three work on the same project folder, so you can extract from a script and review in the
browser.

## Where next

<div class="grid cards" markdown>

- **[Tutorial](tutorial.md)** — build a small PET glycolysis dataset from real papers, start
  to finish, in about 15 minutes.
- **[Use RWTH KI:connect](how-to/rwth.md)** — get a free key and use it.
- **[Add papers in any format](how-to/add-papers.md)** — PDF, XML from Europe PMC or
  Elsevier, HTML, Word.
- **[Command line](reference/cli.md)** and **[Python API](reference/python.md)** reference.

</div>
