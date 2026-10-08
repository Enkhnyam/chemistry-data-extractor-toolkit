# Paper formats

file2records works out a file's format from its contents, so a file with the wrong extension
still reads correctly. In Python, `project.add` takes files and folders, and searches
folders, including subfolders, for files it can read.

| Format | Typical source | Notes |
|---|---|---|
| JATS XML | PubMed Central, Europe PMC, RSC, Springer Nature, MDPI, Frontiers | Tables keep their rows and columns. |
| Elsevier XML | The ScienceDirect article API | Table footnotes stay with their table. |
| HTML | An article page saved from a browser | The page's citation tags supply the DOI and title. |
| Word (`.docx`) | Theses and preprints | Headings, paragraphs, and tables. |
| Markdown, text | Anything you converted yourself | |
| PDF | Everything else | Pages are read by layout recognition, tables included. |
| Other XML | | Read by a general reader and labeled as general XML. |

If a publisher offers both XML and PDF, use the XML. Its tables are already rows and
columns, while a PDF's tables have to be reconstructed from the page layout.

## Download XML from Europe PMC

Europe PMC serves open-access papers without an account:

```bash
curl -o PMC8877978.xml \
  "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC8877978/fullTextXML"
```

To find papers, search [europepmc.org](https://europepmc.org) with the open access filter,
or use its [REST API](https://europepmc.org/RestfulWebService).

<!-- vale Google.Headings = NO -->
## Download Elsevier XML
<!-- vale Google.Headings = YES -->

You need a key from the [Elsevier Developer Portal](https://dev.elsevier.com), and your
institution needs access to the journal:

```bash
curl -H "X-ELS-APIKey: $ELSEVIER_KEY" -H "Accept: text/xml" -o paper.xml \
  "https://api.elsevier.com/content/article/doi/10.1016/j.polymdegradstab.2020.109000?view=FULL"
```

Elsevier's terms let you mine these papers but not share them. See
[Share a dataset](../run/export.md#share-a-dataset).

## Troubleshooting

"Reading PDFs needs docling"
:   The PDF reader didn't install completely. Run `pip install --force-reinstall file2records`.

The first PDF fails with a connection error
:   The PDF reader downloads its layout models the first time it reads a PDF. Connect to the
    internet, or a network without a firewall in the way, and add the PDF again.

"no article body, probably an abstract-only record"
:   Europe PMC only has the abstract for this paper, because it isn't open access there.

"Elsevier XML without the article text"
:   The download used the metadata view. Add `?view=FULL` to the URL.

One file failed
:   The other files were still added. Fix or remove the file and run `add` again. Files that
    are already in the project are skipped.
