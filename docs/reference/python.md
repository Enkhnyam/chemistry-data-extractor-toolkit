# Python API

```python
import file2records as fr
```

## `fr.Project(path="workspace")`

A project folder, the same one the browser app shows. The folder is created if it doesn't exist.

### Settings

| Attribute | Get / set |
|---|---|
| `project.schema` | A list of `{"name", "type", "description"}`. Set it to a list, a path to a JSON file, or a pydantic model class. |
| `project.prompt` | The extraction prompt. Set it to text, or to a `Path` to a text file. |
| `project.rubric` | The judge rubric. Set it the same way as `prompt`. |

### Papers

| Method | Returns |
|---|---|
| `add(*paths, source_tracking=True, on_file=None)` | One dict per file with `id`, `filename`, `format`, `doi` and `n_chunks`, or with `error` if the file couldn't be read. |
| `papers()` | One dict per paper with `id`, `filename`, `format`, `doi`, `title`, `extracted`, `judged` and `n_records`. |
| `search(pattern, ignore_case=True)` | The papers whose text matches, most matches first. Each has a `matches` count and up to three `snippets`. |
| `select(only=None, exclude=None)` | The IDs of the papers that match `only` and don't match `exclude`. |

### Model stages

| Method | Does |
|---|---|
| `check(stage="extract", model=None)` | A list of what's missing. An empty list means ready. |
| `extract(model=None, *, only=None, exclude=None, redo=False, on_paper=None)` | Extracts the papers that aren't done yet and returns one result dict per paper. |
| `judge(model=None, *, only=None, exclude=None, redo=False, on_paper=None)` | Checks the extracted papers that aren't judged yet. |

`model` is usually left out: then the model chosen in the browser's settings is used, or the
one `FILE2RECORDS_API_KEY` and `FILE2RECORDS_ENDPOINT` lead to. Otherwise pass `fr.connect(...)`,
part of a model name such as `"mistral"`, or a full litellm model string. If a stage isn't ready, it raises `RuntimeError` with a list of what's
missing. If one paper fails, its result has an `error` and the other papers still run.

### Results

| Method | Returns |
|---|---|
| `records(*, only=None, exclude=None)` | One dict per record with `doi`, `title`, your fields, `source_chunk_ids`, `judge_verdict`, `judge_critique` and more. |
| `export(path, *, only=None, exclude=None, include_text=False, include_files=False)` | Writes a `.csv` file, a `.json` file or a `.zip` bundle, and returns its path. |

## `fr.connect(api_key=None, endpoint=None, model=None)`

A model from your key, plus the endpoint for services such as RWTH KI:connect. It asks the
service which models it has and picks one, or the one whose name contains `model`. Without
arguments it reads `FILE2RECORDS_API_KEY` and `FILE2RECORDS_ENDPOINT`. Raises `RuntimeError`
if the key is rejected or the endpoint can't be reached.

## `fr.rwth(name=None, api_key=None)`

The same for RWTH KI:connect, with the endpoint filled in. The key comes from `RWTH_API_KEY`
unless you pass `api_key`.

## Errors

| Raised | When |
|---|---|
| `ValueError` | A regex that isn't valid, an export path with an unknown extension, or a schema with a mistake in it. |
| `RuntimeError` | A stage that isn't ready. The message lists what's missing. |
| `FileNotFoundError` | A path given to `add` doesn't exist. |
