# Command line

Every command takes the project folder as its first argument and creates the folder if it
doesn't exist.

Commands that call a model find it through `FILE2RECORDS_API_KEY`, plus
`FILE2RECORDS_ENDPOINT` for services such as RWTH KI:connect, or through the model chosen in
the browser's settings. They read these from your shell, from the `.env` file in the project
folder, and from the `.env` file in the current folder. The model is picked for you. To choose
another, pass `--model` with part of its name, such as `mistral`.

## `serve`

Open the browser app on a project.

```bash
file2records serve [folder] [--port 8000] [--host 127.0.0.1] [--no-browser]
```

`folder` defaults to `workspace`. A new, empty folder opens with the demo project in it. The
app has no login, so keep the default host, which only accepts connections from your own
computer.

## `add`

Read paper files, or folders of them, into the project.

```bash
file2records add folder paths... [--no-source-tracking]
```

With `--no-source-tracking`, chunks aren't tagged, so records can't say which passage a value came from.

## `papers`

List the papers in the project with their ID, format, stage, number of records, and DOI.

```bash
file2records papers folder
```

## `search`

Search the full text of every paper with a regular expression. This doesn't call a model.

```bash
file2records search folder pattern [--case-sensitive]
```

## `check`

List what's missing before `extract` or `judge` can run. The exit code is 1 if extraction isn't ready.

```bash
file2records check folder [--model MODEL]
```

## `extract`

Extract records from papers not extracted yet.

```bash
file2records extract folder [--model MODEL] [--only REGEX] [--exclude REGEX] [--redo]
```

## `judge`

Use a second model to check the records of each extracted paper.

```bash
file2records judge folder [--model MODEL] [--only REGEX] [--exclude REGEX] [--redo]
```

## `export`

Write records to `.csv` or `.json`, or the full bundle to `.zip`.

```bash
file2records export folder output [--only REGEX] [--exclude REGEX] [--include-text] [--include-files]
```

`--include-text` and `--include-files` add the paper text and the source files to a bundle.
Use them only for papers you're allowed to share.

## Options shared by several commands

| Option | Meaning |
|---|---|
| `--model MODEL` | part of a model name, such as `mistral`, or a full litellm model string |
| `--only REGEX` | only papers whose full text matches |
| `--exclude REGEX` | skip papers whose full text matches |
| `--redo` | also re-run papers already done |

`file2records --help` and `file2records <command> --help` show the same information, with examples.
