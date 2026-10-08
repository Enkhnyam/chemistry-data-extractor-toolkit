# Install

You need Python 3.10 or later. To check, open a terminal and run `python3 --version`, or
`py --version` on Windows.

## Install the package

Install file2records into a **virtual environment**: a folder that keeps its packages apart
from the rest of your computer. Run these in the folder you'll work in:

=== "Linux and macOS"

    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    pip install file2records
    ```

=== "Windows"

    ```powershell
    py -m venv .venv
    .venv\Scripts\activate
    pip install file2records
    ```

This installs everything, including the PDF reader, which recognizes the layout of each
page and its tables. The PDF reader needs PyTorch, so on Linux the install is about 6 GB and
can take half an hour. On macOS and Windows it's about 2 GB.

??? note "Linux without an NVIDIA graphics card? Save about 4 GB"
    On Linux, PyTorch comes with NVIDIA's graphics card libraries by default. Without an
    NVIDIA card, install the smaller CPU version of PyTorch first, then file2records:

    ```bash
    pip install torch --index-url https://download.pytorch.org/whl/cpu
    pip install file2records
    ```

    On macOS and Windows, the default PyTorch is already the smaller one.

!!! warning "Activate it in every new terminal"
    The `activate` line only lasts until you close the terminal. In a new terminal, go to
    the same folder and run it again before using file2records. Your prompt shows `(.venv)`
    while it's active.

??? note "Why not `pip install` directly?"
    On many Linux systems, `pip install` outside a virtual environment stops with
    *externally-managed-environment*. The virtual environment avoids that, and keeps
    file2records' packages from interfering with other Python programs.

!!! success "You should see"
    ```console
    $ file2records --version
    file2records 0.3.0
    ```

## Look around before you set anything up

```bash
file2records serve
```

Your browser opens on a finished example with one paper. Its records are already extracted
and judged. You don't need an API key to look at it.

Continue with [API key and endpoint](api-key.md).
