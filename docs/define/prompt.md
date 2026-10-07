# Extraction prompt

The fields say what a record looks like. The **prompt** says which records to make: what
counts as one experiment, and what to leave out. A good prompt answers four questions:

1. **What is one record?** For example, one row of a results table.
2. **What should be skipped?** Values from other papers, values only in figures, and
   predictions instead of measurements.
3. **What applies to several rows?** Conditions given once in a caption or footnote.
4. **What if a value is missing?** Leave it empty. Never 0, and never a guess.

For the example papers, use this prompt:

```text title="prompt.txt"
Extract every CO2 hydrogenation experiment this paper reports. One
record per catalyst and reaction condition; each row of a results table
is one record.

Skip values quoted from other papers, values shown only in figures, and
theoretical calculations. Conditions stated once for a whole table apply
to every row of it.

If the paper doesn't report a value, use null. Never use 0 for a missing
value. Conversion and selectivity are different fields; never put one in
the other.
```

## Set the prompt

=== "Browser"

    1. Click **Extract** at the top of the page.
    2. Next to **Extraction prompt**, click **Write**.
    3. Paste the prompt into the box, and click **Save prompt**.

    !!! success "You should see"
        ![The extraction prompt](../img/tutorial/06-prompt.png)

    !!! tip "Start from an example"
        The empty box shows a complete prompt for another chemistry topic in gray.
        **Start from the example** copies it into the box so you can adapt it.

=== "Python"

    Save the prompt as `prompt.txt` next to your script, and load it:

    ```python
    from pathlib import Path

    project.prompt = Path("prompt.txt")
    ```

    ??? note "Or write the prompt into the script"
        ```python
        project.prompt = """Extract every CO2 hydrogenation experiment this paper reports.
        One record per catalyst and reaction condition; each row of a results table
        is one record."""
        ```

!!! warning "Don't copy answers into the prompt"
    If the prompt contains values from the papers you extract, the model gets those papers
    right for the wrong reason. Use made-up names, such as Cat-A, in any example.

[Write better fields and prompts](../guides/prompts.md) has more advice.

Continue with [Worked examples](examples.md), or skip to [Judge rubric](rubric.md).
