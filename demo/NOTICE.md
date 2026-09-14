# The demo papers, and why they are here

This folder ships two real papers so that a fresh clone has something to run on. Both are
open access under **CC BY 4.0**, on the *publisher's own published version* — which is what
makes redistributing the PDF itself lawful, rather than only the right to read it.

| File | Citation | Licence |
|---|---|---|
| `pdfs/…cholinium-ionic-liquids…pdf` | Salvatore Marullo, Carla Rizzo, Nadka T. Dintcheva and Francesca D'Anna, *Amino Acid-Based Cholinium Ionic Liquids as Sustainable Catalysts for PET Depolymerization*, **ACS Sustainable Chem. Eng.** 2021, **9**, 15157–15165. [10.1021/acssuschemeng.1c04060](https://doi.org/10.1021/acssuschemeng.1c04060) | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) |
| `pdfs/…lewis-acidic…pdf` | Qun Feng Yue, Lin Fei Xiao, Mi Lin Zhang and Xue Feng Bai, *The Glycolysis of Poly(ethylene terephthalate) Waste: Lewis Acidic Ionic Liquids as High Efficient Catalysts*, **Polymers** 2013, **5**, 1258–1271. [10.3390/polym5041258](https://doi.org/10.3390/polym5041258) | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) |

Both PDFs and the text derived from them under `parsed/` are redistributed unmodified in
substance under CC BY 4.0. The rows above are the attribution that licence requires: creator,
title, source and licence, each with a link.

CC BY requires attribution and nothing else: you may redistribute and adapt these files,
including commercially, provided the creators are credited as above.

One caveat on the ACS copy: it carries the publisher's download watermark, which records the IP
address the file was fetched from and links to their sharing guidelines. The article is CC BY, so
redistribution is permitted either way, but a clean copy fetched from the publisher would be
tidier. Replace it and re-run `scripts/build_demo.py` if you want that.

The rest of this repository is MIT (see `LICENSE`). These two PDFs are not MIT; they stay
under CC BY, and the MIT licence does not extend to them.

## Why only two

The PET database this toolkit was generalised out of uses seven papers as redistributable
worked examples. Five of those seven are open access only as a **submitted-version deposit**
in an institutional repository (mostly `ir.ipe.ac.cn`), under CC BY-NC-SA. That licence
covers the deposited manuscript, not the publisher's typeset PDF, and it is the publisher's
PDF that exists on disk. Redistributing the text of those five is fine and is what the
database does; redistributing the publisher's PDF is not, so they are not shipped here.

The two above are the only ones of the seven whose *published* version is CC-licensed.
