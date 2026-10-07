# Command line

Every command takes the **project folder** first; it is created if it doesn't exist. Commands
that call a model use the model chosen in the browser's Settings unless you pass `--model`:
any [litellm model string](https://docs.litellm.ai/docs/providers), or `rwth/<name>`.

Keys are read from the shell, from `.env` in the project folder, and from `.env` in the
current folder.

## serve

Open the browser app on a project.

```bash
file2records serve [folder] [--port 8000] [--host 127.0.0.1] [--no-browser]
```

`folder` defaults to `workspace`. A new, empty folder opens on the demo project. There is no
login, so keep the default host.

## add

Read paper files, or folders of them, into the project.

```bash
file2records add folder paths... [--no-source-tracking]
```

`--no-source-tracking` leaves chunks untagged, so records won't cite where a value came from.

## papers

List the papers in the project: id, format, stage, record count, DOI.

```bash
file2records papers folder
```

## search

Search every paper's full text with a regular expression. Free.

```bash
file2records search folder pattern [--case-sensitive]
```

## check

Say what is missing before `extract` or `judge` can run. Exits with 1 if extraction isn't ready.

```bash
file2records check folder [--model MODEL]
```

## extract

Extract records from papers not extracted yet.

```bash
file2records extract folder [--model MODEL] [--only REGEX] [--exclude REGEX] [--redo]
```

## judge

Have a second model audit each extracted paper's records.

```bash
file2records judge folder [--model MODEL] [--only REGEX] [--exclude REGEX] [--redo]
```

## export

Write records to `.csv` or `.json`, or the full bundle to `.zip`.

```bash
file2records export folder output [--only REGEX] [--exclude REGEX] [--include-text] [--include-files]
```

`--include-text` and `--include-files` put paper text and source files in a bundle — only for
papers you may redistribute.

## Options shared by several commands

| Option | Meaning |
|---|---|
| `--model MODEL` | litellm model string, or `rwth/<name>` |
| `--only REGEX` | only papers whose full text matches |
| `--exclude REGEX` | skip papers whose full text matches |
| `--redo` | also re-run papers already done |

`file2records --help` and `file2records <command> --help` print the same, with examples.
