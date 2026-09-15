# The demo paper, and why it is here

This folder ships one real paper so that a fresh clone has something to run on. It is open
access under **CC BY 3.0**, on the *publisher's own published version* — which is what makes
redistributing the PDF itself lawful, rather than only the right to read it.

| File | Citation | Licence |
|---|---|---|
| `pdfs/…lewis-acidic…pdf` | Qun Feng Yue, Lin Fei Xiao, Mi Lin Zhang and Xue Feng Bai, *The Glycolysis of Poly(ethylene terephthalate) Waste: Lewis Acidic Ionic Liquids as High Efficient Catalysts*, **Polymers** 2013, **5**, 1258–1271. [10.3390/polym5041258](https://doi.org/10.3390/polym5041258) | [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/) |

The PDF and the text derived from it under `parsed/` are redistributed unmodified in substance.
The row above is the attribution the licence requires: creator, title, source and licence, each
with a link. CC BY 3.0 requires attribution and nothing else: you may redistribute and adapt,
including commercially, provided the creators are credited as above.

The rest of this repository is MIT (see `LICENSE`). This PDF is not MIT; it stays under CC BY,
and the MIT licence does not extend to it.

## Why only one

The PET database this toolkit was generalised out of uses seven papers as redistributable
worked examples. Five of those seven are open access only as a **submitted-version deposit** in
an institutional repository (mostly `ir.ipe.ac.cn`), under CC BY-NC-SA. That licence covers the
deposited manuscript, not the publisher's typeset PDF, and it is the publisher's PDF that exists
on disk. Redistributing the text of those five is fine and is what the database does;
redistributing the publisher's PDF is not, so they are not shipped here.

An earlier version of this demo also shipped *Amino Acid-Based Cholinium Ionic Liquids as
Sustainable Catalysts for PET Depolymerization* (ACS Sustainable Chem. Eng. 2021,
[10.1021/acssuschemeng.1c04060](https://doi.org/10.1021/acssuschemeng.1c04060)). That article is
CC BY 4.0 and redistributing it was lawful, but ACS stamps every PDF download with the IP address
it was fetched from, and publishing that line alongside the file served nobody. Re-downloading
does not help — the stamp is applied to every copy — so the paper was removed rather than
replaced. One paper is enough to show what the tool does.
