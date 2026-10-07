# 4. Add papers

file2records reads PDF, XML, HTML, Word, and Markdown files. It splits each paper into
paragraphs and whole tables, called chunks. Later, every value it extracts records which
chunk it came from.

## Download the example papers

Three open-access papers from Europe PMC, as XML. In the terminal, run:

```bash
mkdir papers
curl -o papers/PMC13614198.xml https://www.ebi.ac.uk/europepmc/webservices/rest/PMC13614198/fullTextXML
curl -o papers/PMC13631360.xml https://www.ebi.ac.uk/europepmc/webservices/rest/PMC13631360/fullTextXML
curl -o papers/PMC12631322.xml https://www.ebi.ac.uk/europepmc/webservices/rest/PMC12631322/fullTextXML
```

On Windows, type `curl.exe` instead of `curl`. To use your own papers instead, put them in
the `papers` folder.

## Add them to the project

=== "Browser"

    1. Click **Parse** at the top of the page.
    2. Click **Choose files** and select the three files in the `papers` folder.
    3. Click **Parse 3 files**.

    After a few seconds the papers appear in the list, each with its DOI:

    ![The three papers in the project](../img/tutorial/05-papers.png)

=== "Python"

    ```python
    for paper in project.add("papers"):
        print(paper["filename"], paper["format"], paper["doi"])
    ```

    ```console
    PMC12631322.xml jats 10.1021/acsomega.5c07005
    PMC13614198.xml jats 10.1021/jacs.6c11100
    PMC13631360.xml jats 10.1038/s41467-026-77347-w
    ```

    `add` takes files or folders. Adding a paper that's already in the project does nothing.

!!! tip "XML or PDF?"
    If a publisher offers both, use the XML: its tables are already rows and columns. For
    where to get XML and how PDFs are read, see [Paper formats](../guides/formats.md).

Continue with [Define the fields](fields.md).
