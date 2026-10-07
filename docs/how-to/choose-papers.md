# Choose papers with a regex

Literature searches return papers you don't want. A search for PET glycolysis also finds
studies that use positron emission tomography to measure glycolysis in tumors. You can
leave those out by what their text says, before you send anything to a model.

## Search the text

```console
$ file2records search my-review "BHET yield"

PMC12587479.xml  (16 matches)
    …ia the NaBH4 route showed the best performance, achieving a [BHET yield] of 97% with just 1% catalyst at 180 °C within a reaction ti…
    … al. reported that cobalt–aluminium mixed oxides produced a [BHET yield] of 69%.25 Ultra small cobalt nanoparticles were found to fu…

2 papers, 38 matches
```

In the browser, use the **Search the full text** box on the **Parse** page. Click a snippet
to open the paper at that passage.

## Limit a run to some papers

`--only` keeps papers whose text matches a pattern. `--exclude` then removes papers whose
text matches a second pattern. Both work with `extract`, `judge` and `export`.

```bash
file2records extract my-review --only "glycoly[sz]is" --exclude "tumou?r|positron|tomograph"
```

```python
project.extract(only=r"glycoly[sz]is", exclude=r"tumou?r|positron|tomograph")
```

In the browser, the **Extract** and **Judge** pages have the same two boxes at the top of
the paper list.

## Useful patterns

| Pattern | Matches |
|---|---|
| `glycoly[sz]is` | glycolysis and glycolyzis |
| `methanoly[sz]is\|hydroly[sz]is` | either word |
| `tumou?r` | tumor and tumour |
| `\bFDG\b` | FDG as a whole word |
| `ionic liquids?` | ionic liquid and ionic liquids |
| `BHET\s+yield` | BHET yield with any spacing between the words |

Matching ignores case. To match case, use `--case-sensitive` with `search`, or
`ignore_case=False` in Python.
