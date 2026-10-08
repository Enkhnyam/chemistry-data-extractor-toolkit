# Get started

![How file2records works: parse, extract, judge, review](img/pipeline.svg)

file2records turns papers into a table of records in four stages. It **parses** each paper
into paragraphs and tables, a language model **extracts** the fields you defined, a second
pass **judges** every record against the paper, and you **review** the result and export it.

Before the first run you set up a few things. This page lists them in the order you need
them. Each card links to a page with screenshots and code.

!!! tip "Browser or Python?"
    Every page shows both. The browser app is easiest for setting things up and for
    reviewing. Python is best for choosing papers and for running many papers. Both work on
    the same project folder, so you can switch at any time.

## 1. Set up, once

<div class="grid cards" markdown>

-   :lucide-download:{ .lg .middle } **[Install](setup/install.md)**

    ---

    One `pip install`, PDF reader included.

-   :lucide-key-round:{ .lg .middle } **[API key and endpoint](setup/api-key.md)**

    ---

    Get access to a language model from your AI service, and save it in a `.env` file.

-   :lucide-cpu:{ .lg .middle } **[Extraction and judge models](setup/models.md)**

    ---

    Choose which model extracts and which one checks.

-   :lucide-files:{ .lg .middle } **[Papers and the parser](setup/papers.md)**

    ---

    Add PDF, XML, HTML, or Word files to a project.

</div>

## 2. Define what to extract, per project

<div class="grid cards" markdown>

-   :lucide-table-2:{ .lg .middle } **[Fields](define/fields.md)**

    ---

    The columns of your dataset: name, type, and description. Chemicals can get ChEBI
    identifiers.

-   :lucide-message-square-text:{ .lg .middle } **[Extraction prompt](define/prompt.md)**

    ---

    What counts as one record, and what to leave out.

-   :lucide-book-open-check:{ .lg .middle } **[Worked examples](define/examples.md)**

    ---

    Optional. Show the model one example done right.

-   :lucide-scale:{ .lg .middle } **[Judge rubric](define/rubric.md)**

    ---

    What makes a record right or wrong.

</div>

## 3. Run and review

<div class="grid cards" markdown>

-   :lucide-filter:{ .lg .middle } **[Choose papers](run/choose.md)**

    ---

    Search the papers' text, and pick the ones worth extracting.

-   :lucide-play:{ .lg .middle } **[Extract](run/extract.md)**

    ---

    The model reads each paper and fills in your fields.

-   :lucide-badge-check:{ .lg .middle } **[Judge](run/judge.md)**

    ---

    A second pass checks every record against the paper.

-   :lucide-eye:{ .lg .middle } **[Review](run/review.md)**

    ---

    See each value next to its source, and correct it.

-   :lucide-file-spreadsheet:{ .lg .middle } **[Export](run/export.md)**

    ---

    A CSV file, or a bundle you can share.

</div>

## The example used on every page

The pages use three open-access papers on CO₂ hydrogenation catalysts and six fields:
catalyst, temperature, pressure, CO₂ conversion, main product, and selectivity. Follow along
with them the first time; [All steps in one script](guides/script.md) puts the Python parts
together.
