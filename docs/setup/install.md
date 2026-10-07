# Install

You need Python 3.10 or later. To check, open a terminal and run `python --version`.

## Install the package

```bash
pip install file2records
```

!!! success "You should see"
    ```console
    $ file2records --version
    file2records 0.2.1
    ```

This reads XML, HTML, Word, and Markdown papers, and takes about 350 MB.

## Add the PDF reader, if you need it

```bash
pip install "file2records[pdf]"
```

The PDF reader recognizes the layout of each page, including tables. It needs PyTorch,
which is a download of a few GB.

!!! tip "Prefer XML when you can get it"
    Many publishers offer papers as XML. Its tables are already rows and columns, so they
    come out exactly, and the small install is enough. See
    [Papers and the parser](papers.md).

??? note "No GPU? Save 3 GB"
    On a computer without an NVIDIA graphics card, install the smaller CPU version of
    PyTorch first:

    ```bash
    pip install torch --index-url https://download.pytorch.org/whl/cpu
    pip install "file2records[pdf]"
    ```

## Look around before you set anything up

```bash
file2records serve
```

Your browser opens on a finished example with one paper. Its records are already extracted
and judged. You don't need an API key to look at it.

Continue with [API key and endpoint](api-key.md).
