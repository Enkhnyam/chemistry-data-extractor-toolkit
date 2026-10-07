# Papers and the parser

file2records reads PDF, XML, HTML, Word, and Markdown files. The parser splits each paper
into paragraphs and whole tables, called **chunks**. Later, every value the model extracts
records which chunk it came from, so you can check it against the source.

## Get the example papers

Three open-access papers from Europe PMC, as XML. In the terminal, run:

```bash
mkdir papers
curl -o papers/PMC13614198.xml https://www.ebi.ac.uk/europepmc/webservices/rest/PMC13614198/fullTextXML
curl -o papers/PMC13631360.xml https://www.ebi.ac.uk/europepmc/webservices/rest/PMC13631360/fullTextXML
curl -o papers/PMC12631322.xml https://www.ebi.ac.uk/europepmc/webservices/rest/PMC12631322/fullTextXML
```

On Windows, type `curl.exe` instead of `curl`.

## Add papers to the project

=== "Browser"

    1. Click **Parse** at the top of the page.
    2. Click **Choose files**, or **Choose a whole folder**, and select the papers.
    3. Click **Parse 3 files**.

    !!! success "You should see"
        ![The three papers in the project](../img/tutorial/05-papers.png)

=== "Python"

    ```python
    for paper in project.add("papers"):
        print(paper["filename"], paper["format"], paper["doi"])
    ```

    !!! success "You should see"
        ```console
        PMC12631322.xml jats 10.1021/acsomega.5c07005
        PMC13614198.xml jats 10.1021/jacs.6c11100
        PMC13631360.xml jats 10.1038/s41467-026-77347-w
        ```

    `add` takes files and folders, including subfolders.

Adding a paper that's already in the project does nothing, so you can add a folder again
after putting new papers in it.

## Which formats work, and how well

file2records recognizes each format from the file's contents, not its name.

| Format | Typical source | How it's read |
|---|---|---|
| JATS XML | PubMed Central, Europe PMC, RSC, Springer Nature, MDPI | Exactly, tables included |
| Elsevier XML | ScienceDirect's article API | Exactly; table footnotes stay with their table |
| HTML | An article page saved from the browser | Text and tables; DOI from the page's tags |
| Word (`.docx`) | Theses and preprints | Headings, paragraphs, and tables |
| Markdown, text | Anything you converted yourself | As written |
| PDF | Everything else | Layout recognition; needs `file2records[pdf]` |

!!! tip "XML gives the best tables"
    If a publisher offers XML and PDF, use the XML. Its tables are already rows and
    columns, while a PDF's tables have to be reconstructed from the page layout.
    [Paper formats](../guides/formats.md) shows how to download XML from Europe PMC and
    Elsevier.

!!! warning "Reading PDFs needs the PDF extra"
    Without it, adding a PDF gives an error that starts with *Reading PDFs needs the PDF
    extra*. Install it with `pip install "file2records[pdf]"`. The other files are still added.

Continue with [Fields](../define/fields.md).
