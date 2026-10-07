# 7. Choose which papers to extract

A literature search returns papers you don't want, such as papers on a different reaction
that use the same words. Sending them to the model costs time and
gives records you have to throw away. Instead, choose papers by what their text says.
Searching costs nothing, because no model is involved.

The patterns are regular expressions. The ones you need most:

| Pattern | Matches |
|---|---|
| `methanation` | the word methanation |
| `methanation\|hydrogenation` | either word |
| `hydrogenat(ion\|ed)` | hydrogenation and hydrogenated |
| `electrocatalytic\|electroreduction` | papers on electrochemical CO2 reduction |
| `\bDFT\b` | DFT as a whole word, not inside another word |
| `CO2\s+conversion` | CO2 conversion with any spacing |

Matching ignores upper and lower case.

## Search the papers

=== "Python"

    ```python
    for hit in project.search(r"CO2\s+conversion"):
        print(hit["matches"], hit["title"])
    ```

    ```console
    44 Influence of Basic Solution on Carbonaceous Alumina Supported Nickel Catalysts for CO2 Methanation
    7 Nickel–Zinc Catalysts Favor CO Production via Carbide Formation in CO2 Hydrogenation
    7 Trace Al/Rb regulation stabilizes Cu-Fe5C2 active sites for ambient-pressure photothermal CO2 hydrogenation to C2-C4 olefin
    ```

    Each result also has `snippets`: the text around the first matches, to see whether the
    paper is relevant.

=== "Browser"

    On the **Parse** page, type the pattern into **Search the full text** and click
    **Search**. Click a snippet to open the paper at that passage.

## Choose papers by their text

`only` keeps the papers whose text matches a pattern. `exclude` then removes the papers whose
text matches a second pattern.

=== "Python"

    ```python
    chosen = project.select(only=r"hydrogenation|methanation", exclude=r"electrocatalytic|electroreduction")
    print(chosen)
    ```

    ```console
    ['pmc12631322-05a5c716', 'pmc13614198-d3bc8887', 'pmc13631360-011f2613']
    ```

    In the next step, pass the same `only` and `exclude` to `extract`.

=== "Browser"

    On the **Extract** page, type the patterns into the two boxes above the paper list, and
    click **Select**. The matching papers are ticked.

All three example papers match. With your own papers, check the list before you extract.

!!! warning "Search before you exclude"
    Papers mention neighboring topics in passing, often in the introduction. Excluding the
    example papers by `photocatalytic` would drop the Cu-Fe5C2 paper, which is about
    photothermal CO2 hydrogenation but mentions photocatalytic work once. Search for the word
    first, and exclude only by words the unwanted papers use and the wanted ones don't.

Continue with [Extract the records](extract.md).
