# Extract

The model reads each chosen paper and fills in your fields. It sends one request per paper,
which takes between a few seconds and a minute.

=== "Browser"

    1. Click **Extract** at the top of the page. Every item under **What this run needs**
       has a green check:

        ![Ready to extract](../img/tutorial/07-extract-ready.png)

    2. Check that the papers you want are ticked.
    3. Click **Run extraction on selected**. You can switch to other pages while it runs.

    !!! success "You should see"
        ![Extraction finished](../img/tutorial/08-extract-done.png)

=== "Python"

    ```python
    results = project.extract(
        only=r"hydrogenation|methanation",
        exclude=r"electrocatalytic|electroreduction",
    )

    for result in results:
        print(result["id"], result.get("n_records"), result.get("error", ""))
    ```

    !!! success "You should see"
        ```console
        pmc12631322-05a5c716 32
        pmc13614198-d3bc8887 11
        pmc13631360-011f2613 26
        ```

    To print each paper as soon as it's done, add `on_paper=print`.

!!! info "Run it again any time"
    Papers that are already extracted are skipped, so you can run it again after adding
    papers. To extract a paper again, for example after changing the prompt, pass
    `redo=True` in Python, or delete its extraction under **Review** in the browser.

!!! note "The numbers vary"
    A language model doesn't answer exactly the same way twice, so the number of records can
    differ a little from run to run.

## If a paper fails

A failed paper shows an error, and the other papers still run.

"did not match the schema"
:   The model's answer was cut off or malformed, usually because of a very large table. Run
    it again, or use a model with a larger maximum output.

0 records
:   The paper reports none of the experiments your prompt asks for. That's normal for review
    articles and theory papers.

Continue with [Judge](judge.md).
