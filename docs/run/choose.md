# Choose papers

A literature search returns papers you don't want, such as papers on a different reaction
that use the same words. Sending them to the model costs time and gives records you have to
throw away. So first choose papers by what their text says. This doesn't call a model, so
it's free and instant.

The patterns are regular expressions. The ones you need most:

| Pattern | Matches |
|---|---|
| `methanation` | the word methanation, in any case |
| `methanation\|hydrogenation` | either word |
| `hydrogenat(ion\|ed)` | hydrogenation and hydrogenated |
| `electrocatalytic\|electroreduction` | papers on electrochemical CO2 reduction |
| `\bDFT\b` | DFT as a whole word, not inside another word |
| `CO2\s+conversion` | CO2 conversion with any spacing |

## 1. Search

See which papers mention something, and how often.

=== "Python"

    ```python
    for hit in project.search(r"CO2\s+conversion"):
        print(hit["matches"], hit["title"][:60])
    ```

    !!! success "You should see"
        ```console
        44 Influence of Basic Solution on Carbonaceous Alumina Support
        7 Nickel–Zinc Catalysts Favor CO Production via Carbide Forma
        7 Trace Al/Rb regulation stabilizes Cu-Fe5C2 active sites for
        ```

    Each result also has `snippets`, the text around the first matches:

    ```python
    hit = project.search(r"CO2\s+conversion")[0]
    print(hit["snippets"][0]["match"], "…", hit["snippets"][0]["after"][:50])
    ```

=== "Browser"

    On the **Parse** page, type the pattern into **Search the full text**, and click
    **Search**. Click a snippet to open the paper at that passage.

## 2. Choose

`only` keeps the papers whose text matches. `exclude` then removes the papers whose text
matches a second pattern.

=== "Python"

    ```python
    chosen = project.select(
        only=r"hydrogenation|methanation",
        exclude=r"electrocatalytic|electroreduction",
    )
    print(len(chosen), "papers chosen")
    ```

    !!! success "You should see"
        ```console
        3 papers chosen
        ```

    Pass the same `only` and `exclude` to [extract](extract.md), [judge](judge.md), and
    [export](export.md).

=== "Browser"

    On the **Extract** page, type the patterns into the two boxes above the paper list, and
    click **Select**. The matching papers are ticked.

!!! warning "Search before you exclude"
    Papers mention neighboring topics in passing, often in the introduction. Excluding the
    example papers by `photocatalytic` would drop the Cu-Fe5C2 paper, which is about
    photothermal CO2 hydrogenation but mentions photocatalytic work once. Search for the word
    first, and exclude only by words the unwanted papers use and the wanted ones don't.

Continue with [Extract](extract.md).
