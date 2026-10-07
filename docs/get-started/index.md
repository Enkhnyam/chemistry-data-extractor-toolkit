# Get started

![How file2records works: parse, extract, judge, review](../img/pipeline.svg)

file2records turns papers into a table of records in four stages. It **parses** each paper
into paragraphs and tables, a language model **extracts** the fields you defined, a second
pass **judges** every record against the paper, and you **review** the result and export it.

These pages take you through it once, in order, with three real papers on CO₂ hydrogenation
catalysts. Each step shows how to do it in the browser and in Python. Use whichever you
prefer, or mix them: both work on the same project folder.

1. [Install file2records](install.md)
2. [Set up API access](api-access.md)
3. [Create a project](project.md)
4. [Add papers](papers.md)
5. [Define the fields](fields.md)
6. [Write the extraction prompt](prompt.md)
7. [Choose which papers to extract](choose.md)
8. [Extract the records](extract.md)
9. [Judge and review the records](judge.md)
10. [Export the dataset](export.md)

[All steps in one script](script.md) puts the Python parts together.

## What you need

- A computer with Python 3.10 or later. To check, open a terminal and run
  `python --version`.
- API access to a language model. [Step 2](api-access.md) explains how to get it.

It takes about 20 minutes.
