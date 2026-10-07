# 1. Install file2records

Open a terminal and run:

```bash
pip install file2records
```

Check that it worked:

```console
$ file2records --version
file2records 0.2.1
```

This installs everything for XML, HTML, Word and Markdown papers, about 350 MB.

!!! tip "Reading PDFs"
    To read PDF files too, install the PDF extra instead:

    ```bash
    pip install "file2records[pdf]"
    ```

    It adds a PDF reader that needs PyTorch, a download of a few GB. The papers in this
    guide are XML, so you can skip it for now.

Continue with [Set up API access](api-access.md).
