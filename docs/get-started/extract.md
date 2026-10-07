# 8. Extract the records

Now the model reads each chosen paper and fills in your fields. It sends one request per
paper, which takes between a few seconds and a minute.

=== "Browser"

    1. Click **Extract** at the top of the page. Every item under **What this run needs**
       has a green check:

        ![Ready to extract](../img/tutorial/07-extract-ready.png)

    2. Make sure the papers you chose in step 7 are ticked.
    3. Click **Run extraction on selected**. When it's done, each paper shows how many
       records it gave:

        ![Extraction finished](../img/tutorial/08-extract-done.png)

    You can switch to other pages while it runs.

=== "Python"

    ```python
    results = project.extract(only=r"hydrogenation|methanation",
                              exclude=r"electrocatalytic|electroreduction")
    for r in results:
        print(r["id"], r.get("n_records"), r.get("error", ""))
    ```

    ```console
    pmc12631322-05a5c716 24
    pmc13614198-d3bc8887 10
    pmc13631360-011f2613 15
    ```

    To see each paper as soon as it's done, add `on_paper=print`.

Papers that are already extracted are skipped, so you can run it again after adding more
papers. To extract a paper again, for example after changing the prompt, delete its
extraction on the **Extract** page, or pass `redo=True` in Python.

The numbers vary from run to run: a language model doesn't answer exactly the same way twice.

## If a paper fails

A failed paper shows an error, and the other papers still run.

"did not match the schema"
:   The model's answer was cut off or malformed. This happens with very large tables. Run it
    again, or use a model with a larger maximum output.

0 records
:   The paper reports none of the experiments your prompt asks for. That's normal for review
    articles and theory papers.

Continue with [Judge and review the records](judge.md).
