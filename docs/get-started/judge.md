# 9. Judge and review the records

A model makes mistakes: a value from the wrong row, a number from another paper, conversion
in the selectivity field. So a second pass, called the judge, reads each paper again
and checks every record against it. It marks each record **correct** or **incorrect**, explains why,
and suggests corrected values. It never changes anything itself: you decide.

The judge needs a rubric, which says what makes a record right or wrong. For the example,
use this:

```text
Check each record against the paper. A record is correct if every value
matches the experiment it describes.

A record is wrong if a value belongs to a different experiment, comes
from another paper, or puts conversion where selectivity belongs (or the
reverse). For a wrong record, give the correct value and quote the
sentence or table row that shows it.
```

## Run the judge

=== "Browser"

    1. Click **Judge** at the top of the page.
    2. Next to **Judge rubric**, click **Write**, paste the rubric, and click **Save prompt**.
    3. Click **Run judge on selected**.

=== "Python"

    ```python
    project.rubric = """Check each record against the paper. A record is correct if every value
    matches the experiment it describes.

    A record is wrong if a value belongs to a different experiment, comes
    from another paper, or puts conversion where selectivity belongs (or the
    reverse). For a wrong record, give the correct value and quote the
    sentence or table row that shows it."""

    project.judge()
    ```

    Only papers that are extracted and not yet judged are sent.

## Review the records

=== "Browser"

    When the judge is done, the **Review** section shows a paper on the left and its records
    on the right. Each record says **correct** or **incorrect**, with the reason underneath:

    ![Reviewing the records](../img/tutorial/09-review.png)

    - Click a record to highlight the passages it came from.
    - If the judge suggests a different value, the field shows it with an **apply** button.
      Nothing changes until you click it.
    - To change a value yourself, click **Edit** on the record, then **Save corrections**.

    Your corrections are saved next to the model's original answer, so you can always
    compare them.

=== "Python"

    ```python
    rows = project.records()
    wrong = [r for r in rows if r["judge_verdict"] == "incorrect"]
    print(len(rows), "records,", len(wrong), "judged incorrect")
    for r in wrong[:3]:
        print("-", r["catalyst"], ":", r["judge_critique"])
    ```

    ```console
    49 records, 11 judged incorrect
    - Ni/ZnO : The record lacks temperature information and gives a precise CO selectivity of 90 % while the paper reports a CO selectivity *above* 90 % over a temperature range of 100–500 °C and does not provide a single temperature‑specific value.
    - Ni/ZnO : Same issues as Record 0 – temperature is missing and selectivity is given as an exact 90 % which does not match the paper’s statement of >90 %.
    - Ni/ZnO : Missing temperature and an overly specific selectivity value; the paper does not give a single selectivity number but reports >90 % across 100–500 °C.
    ```

    Each record is a dictionary with your fields, the paper's `doi`, and the judge's
    `judge_verdict`, `judge_critique` and `judge_proposed`. To correct records, use the
    browser: it shows each value next to its source.

Continue with [Export the dataset](export.md).
