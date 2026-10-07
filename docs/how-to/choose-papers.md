# Choose papers with a regex

Searches return papers you don't want — "PET" is also positron emission tomography,
"glycolysis" is also sugar metabolism. Choose by what each paper's text says before any model
is called. It is free.

## Search

```console
$ file2records search my-review "BHET yield"

PMC12587479.xml  (16 matches)
    …ia the NaBH4 route showed the best performance, achieving a [BHET yield] of 97% with just 1% catalyst at 180 °C within a reaction ti…
    … al. reported that cobalt–aluminium mixed oxides produced a [BHET yield] of 69%.25 Ultra small cobalt nanoparticles were found to fu…

2 papers, 38 matches
```

In the browser it is the **Search the full text** box on the Parse page; click a snippet to
open the passage.

## Run only on the papers you want

`--only` keeps papers whose text matches; `--exclude` then drops papers whose text matches.
Both work on `extract`, `judge` and `export`:

```bash
file2records extract my-review --only "glycoly[sz]is" --exclude "tumou?r|positron|tomograph"
```

```python
project.extract(only=r"glycoly[sz]is", exclude=r"tumou?r|positron|tomograph")
```

In the browser, the Extract and Judge pages have the same two boxes above the paper list.

## Patterns worth knowing

| Pattern | Matches |
|---|---|
| `glycoly[sz]is` | glycolysis, glycolyzis |
| `methanoly[sz]is\|hydroly[sz]is` | either word |
| `tumou?r` | tumor, tumour |
| `\bFDG\b` | FDG as a whole word, not inside another word |
| `ionic liquids?` | ionic liquid, ionic liquids |
| `BHET\s+yield` | BHET yield, with any spacing |

Matching ignores case unless you pass `--case-sensitive` (search) or `ignore_case=False`
(Python).
