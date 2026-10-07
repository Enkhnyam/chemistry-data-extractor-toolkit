# Add papers in any format

```bash
file2records add my-review papers/        # files or folders; folders are searched recursively
```

The format is recognised from the file itself, not its name:

| Format | Where it comes from | Notes |
|---|---|---|
| **JATS XML** | PubMed Central, Europe PMC, RSC, Springer Nature, MDPI, Frontiers… | Tables exact. Works without a DOCTYPE line. |
| **Elsevier XML** | ScienceDirect's article API (`view=FULL`) | Table footnotes stay with their table. |
| **HTML** | a saved article page | `citation_doi` / `citation_title` tags are used. |
| **Word** (`.docx`) | theses, preprints | headings, paragraphs, tables |
| **Markdown, text** | anything you converted yourself | |
| **PDF** | everything else | needs `pip install "file2records[pdf]"` |
| other XML | | read by a general reader, labelled "XML (general)" |

!!! tip "Prefer XML to PDF"
    When a publisher offers both, take the XML. Its tables arrive as rows and cells; a PDF's
    tables have to be reconstructed from the page layout.

## Get XML from Europe PMC

Open-access papers, no key:

```bash
curl -o PMC8877978.xml \
  "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC8877978/fullTextXML"
```

To find papers, search at [europepmc.org](https://europepmc.org) with the *Open access*
filter, or use the [REST API](https://europepmc.org/RestfulWebService).

## Get XML from Elsevier

With a key from [dev.elsevier.com](https://dev.elsevier.com) and your institution's access:

```bash
curl -H "X-ELS-APIKey: $ELSEVIER_KEY" -H "Accept: text/xml" -o paper.xml \
  "https://api.elsevier.com/content/article/doi/10.1016/j.polymdegradstab.2020.109000?view=FULL"
```

Papers you get this way may be mined, not redistributed — see
[Review and export](review-and-export.md#sharing-a-dataset).

## If it goes wrong

- **"Reading PDFs needs the PDF extra"** — `pip install "file2records[pdf]"`.
- **"no article body — probably an abstract-only record"** — Europe PMC has only the abstract
  for that paper; it isn't open access there.
- **"Elsevier XML without the article text"** — you downloaded the metadata view; add
  `?view=FULL`.
- **A file failed** — the others are still added. Fix or remove it and run `add` again;
  re-adding a file that is already there is harmless.
