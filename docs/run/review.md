# Review

Reviewing is where you decide what goes into the dataset. You see each record next to the
passages it came from, with the judge's verdict and suggestions.

=== "Browser"

    Click **Judge** at the top of the page, and scroll to **Review**. Choose a paper: it's
    on the left, and its records are on the right.

    ![Reviewing the records](../img/tutorial/09-review.png)

    - **Click a record** to highlight the passages it came from.
    - **Click a field** to find its value in the text. Click again for the next match.
    - **Click apply** to accept a value the judge suggests. Nothing changes until you do.
      A suggestion that doesn't fit the field, such as a range for a number field, isn't
      offered to apply; the judge's reasoning mentions it instead.
    - **Click Edit** to change a value yourself.
    - **Click looks right or looks wrong**, and add a note, to mark records you checked.

    Then click **Save corrections**.

    !!! info "The original stays"
        Your corrections are saved next to the model's original answer, so you can always
        compare them.

=== "Python"

    Reviewing works best in the browser, where you see each value next to its source. To
    open the project there:

    ```bash
    file2records serve my-project
    ```

    In Python you can read the records, for example to list what the judge flagged:

    ```python
    for row in project.records():
        if row["judge_verdict"] == "incorrect":
            print(row["catalyst"], "→", row["judge_proposed"])
    ```

    !!! success "You should see"
        ```console
        10Ni/C-Al-3NH4OH → temperature_c=None
        0.1Al‑RCF → main_product='C2-4 hydrocarbon'
        ```

    Each record is a dictionary with your fields, the paper's `doi`, and the judge's
    `judge_verdict`, `judge_critique`, and `judge_proposed`.

!!! tip "Where to start"
    Start with the records the judge marked **incorrect**. Most are values the model left
    empty or copied from the wrong row, and the judge's suggestion usually shows the fix.

Continue with [Export](export.md).
