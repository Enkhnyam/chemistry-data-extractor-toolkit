# 6. Write the extraction prompt

The fields say what a record looks like. The prompt says which records to make: what counts
as one experiment, and what to leave out. For the example papers, use this prompt:

```text
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

=== "Browser"

    1. Click **Extract** at the top of the page.
    2. Next to **Extraction prompt**, click **Write**.
    3. Paste the prompt into the box, and click **Save prompt**.

    ![The extraction prompt](../img/tutorial/06-prompt.png)

=== "Python"

    ```python
    project.prompt = """Extract every CO2 hydrogenation experiment this paper reports. One
    record per catalyst and reaction condition; each row of a results table
    is one record.

    Skip values quoted from other papers, values shown only in figures, and
    theoretical calculations. Conditions stated once for a whole table apply
    to every row of it.

    If the paper doesn't report a value, use null. Never use 0 for a missing
    value. Conversion and selectivity are different fields; never put one in
    the other."""
    ```

    You can also keep the prompt in a text file and load it with
    `project.prompt = Path("prompt.txt")`.

## What makes a good prompt

A good prompt answers four questions:

1. **What is one record?** For example, one row of a results table.
2. **What should be skipped?** Values from other papers, values only in figures, and
   predictions instead of measurements.
3. **What applies to several rows?** Conditions given once in a caption or footnote.
4. **What if a value is missing?** Null. Never 0, and never a guess.

[Write better fields and prompts](../guides/prompts.md) has more advice.

Continue with [Choose which papers to extract](choose.md).
