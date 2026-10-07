# Python API

```python
import file2records as fr
```

## `fr.Project(path="workspace")`

A project folder — the same one the browser app shows. Created if it doesn't exist.

### Settings

| Attribute | Get / set |
|---|---|
| `project.schema` | list of `{"name", "type", "description"}`; set it to a list, a `.json` path, or a pydantic model class |
| `project.prompt` | the extraction prompt; set it to text or a `Path` to a text file |
| `project.rubric` | the judge rubric; same as `prompt` |

### Papers

| Method | Returns |
|---|---|
| `add(*paths, source_tracking=True, on_file=None)` | one dict per file: `id`, `filename`, `format`, `doi`, `n_chunks` — or `error` |
| `papers()` | one dict per paper: `id`, `filename`, `format`, `doi`, `title`, `extracted`, `judged`, `n_records` |
| `search(pattern, ignore_case=True)` | papers whose text matches, most matches first, each with `matches` and up to three `snippets` |
| `select(only=None, exclude=None)` | ids of papers matching `only` and not `exclude` |

### Model stages

| Method | Does |
|---|---|
| `check(stage="extract", model=None)` | list of what is missing; empty means ready |
| `extract(model=None, *, only=None, exclude=None, redo=False, on_paper=None)` | extracts papers not done yet; returns one result dict per paper |
| `judge(model=None, *, only=None, exclude=None, redo=False, on_paper=None)` | audits extracted papers not judged yet |

`model` is a litellm model string, `"rwth/<name>"`, `fr.rwth(...)`, a dict of litellm
parameters (`model`, `api_key`, `api_base`, …), or `None` for the model chosen in Settings.
A stage that isn't ready raises `RuntimeError` with what is missing. A paper that fails comes
back with an `error` and the rest carry on.

### Results

| Method | Returns |
|---|---|
| `records(*, only=None, exclude=None)` | one dict per record: `doi`, `title`, your fields, `source_chunk_ids`, `judge_verdict`, `judge_critique`, … |
| `export(path, *, only=None, exclude=None, include_text=False, include_files=False)` | writes `.csv`, `.json` or a `.zip` bundle; returns the path |

## `fr.rwth(name="gpt-oss-120b", api_key=None)`

Parameters for a model on RWTH KI:connect. The key comes from `RWTH_API_KEY` unless given.

## Errors

| Raised | When |
|---|---|
| `ValueError` | a regex that isn't valid, an unknown export extension, a malformed schema |
| `RuntimeError` | a stage that isn't ready (message lists what is missing) |
| `FileNotFoundError` | a path given to `add` doesn't exist |
