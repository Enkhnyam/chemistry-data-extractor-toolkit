"""The Python API: a project folder and the things you do to it.

    import file2records as fr

    project = fr.Project("my-review")
    project.add("papers/")                       # PDF, XML, HTML, Word, Markdown
    project.schema = "schema.json"               # or a list of fields, or a pydantic model
    project.prompt = "Extract every reaction ..."
    project.extract(model=fr.rwth())
    project.export("dataset.csv")

A project is the same folder the web app shows (`file2records serve my-review`), so a run
started here can be reviewed there, and the other way round.

One project is open at a time in a process: every method makes its own project the open one
before it touches anything, so two Project objects can be used one after the other, but not
from two threads at once.
"""
import json
from collections.abc import Callable
from pathlib import Path

from . import bundle, config, filters, pipeline, report, storage

FIELD_TYPES = {str: "string", float: "number", int: "integer", bool: "boolean"}


class Project:
    def __init__(self, path="workspace"):
        self.path = storage.use(path)

    def __repr__(self):
        return f"Project({str(self.path)!r})"

    def _open(self):
        if storage.WORKSPACE != self.path:
            storage.use(self.path)

    # ---------- configuration ----------

    @property
    def schema(self) -> list[dict]:
        """The fields each record has: [{"name", "type", "description"}, ...]."""
        self._open()
        return config.get_schema()

    @schema.setter
    def schema(self, value):
        self._open()
        config.save_schema(_fields(value))

    @property
    def prompt(self) -> str:
        """The extraction prompt: what to pull out of each paper and what to skip."""
        self._open()
        return config.get_extract_prompt()

    @prompt.setter
    def prompt(self, text: str):
        self._open()
        config.save_extract_prompt(_text(text))

    @property
    def rubric(self) -> str:
        """The judge's rubric: what counts as a correct record."""
        self._open()
        return config.get_judge_prompt()

    @rubric.setter
    def rubric(self, text: str):
        self._open()
        config.save_judge_prompt(_text(text))

    # ---------- papers ----------

    def add(self, *paths, source_tracking: bool = True,
            on_file: Callable[[dict], None] | None = None) -> list[dict]:
        """Read files and folders into the project. Re-adding the same file is harmless: a paper
        is identified by its name and content. Returns one result per file; a file that could
        not be read has an "error" and does not stop the others."""
        self._open()
        results = []
        for path in pipeline.collect_files(paths):
            result = pipeline.add_file(path.name, path.read_bytes(), source_tracking)
            results.append(result)
            if on_file:
                on_file(result)
        return results

    def papers(self) -> list[dict]:
        self._open()
        return storage.list_papers()

    def search(self, pattern: str, ignore_case: bool = True) -> list[dict]:
        """Papers whose full text matches a regular expression, with snippets. No model call."""
        self._open()
        return filters.search(pattern, ignore_case)

    def select(self, only: str | None = None, exclude: str | None = None) -> list[str]:
        """Ids of the papers whose text matches `only` and not `exclude` (both regexes)."""
        self._open()
        return filters.select(pipeline.paper_ids(), only, exclude)

    # ---------- the model stages ----------

    def check(self, stage: str = "extract", model=None) -> list[str]:
        """What is missing before `stage` can run. Empty means ready."""
        self._open()
        return pipeline.blockers(stage, None if model is None else
                                 pipeline.resolve_model(model, stage))

    def extract(self, model=None, *, only: str | None = None, exclude: str | None = None,
                redo: bool = False, on_paper: Callable[[dict], None] | None = None) -> list[dict]:
        """Extract records from every paper not extracted yet (all of them with `redo`),
        limited by `only` / `exclude` if given. `model` is a litellm model string,
        "rwth/<name>", fr.rwth(...), or None for the model chosen in the project's settings."""
        return self._run("extract", model, only, exclude, redo, on_paper)

    def judge(self, model=None, *, only: str | None = None, exclude: str | None = None,
              redo: bool = False, on_paper: Callable[[dict], None] | None = None) -> list[dict]:
        """Have a second model audit each extracted paper's records against its text."""
        return self._run("judge", model, only, exclude, redo, on_paper)

    def _run(self, stage, model, only, exclude, redo, on_paper):
        self._open()
        params = pipeline.resolve_model(model, stage)
        missing = pipeline.blockers(stage, None if model is None else params)
        if missing:
            raise RuntimeError(" ".join(missing))
        ids = filters.select(pipeline.paper_ids(), only, exclude)
        if stage == "judge":
            ids = [p for p in ids if pipeline.done("extract", p)]
        if not redo:
            ids = [p for p in ids if not pipeline.done(stage, p)]
        run = pipeline.extract if stage == "extract" else pipeline.judge_papers
        return run(ids, params, on_paper)

    # ---------- results ----------

    def records(self, *, only: str | None = None, exclude: str | None = None) -> list[dict]:
        """Every record, one dict per row, with its paper's DOI and the judge's verdict."""
        self._open()
        return report.flat_records(self._chosen(only, exclude))[1]

    def export(self, path, *, only: str | None = None, exclude: str | None = None,
               include_text: bool = False, include_files: bool = False) -> Path:
        """Write records to .csv or .json, or the full bundle to .zip. Paper text goes into a
        bundle only with include_text -- see bundle.py on licences."""
        self._open()
        path = Path(path)
        chosen = self._chosen(only, exclude)
        if path.suffix.lower() == ".zip":
            path.write_bytes(bundle.build(chosen, include_text=include_text,
                                          include_files=include_files))
        elif path.suffix.lower() == ".json":
            path.write_text(json.dumps(report.flat_records(chosen)[1], indent=1,
                                       ensure_ascii=False), encoding="utf-8")
        elif path.suffix.lower() == ".csv":
            path.write_bytes(bundle.csv_bytes(*report.flat_records(chosen)))
        else:
            raise ValueError(f"Export to .csv, .json or .zip, not {path.suffix or 'no extension'}.")
        return path

    def _chosen(self, only, exclude):
        return filters.select(pipeline.paper_ids(), only, exclude) if (only or exclude) else None


def rwth(name: str = pipeline.RWTH_DEFAULT, api_key: str | None = None) -> dict:
    """A model on RWTH's KI:connect (free for its open models). Key from RWTH_API_KEY."""
    return pipeline.rwth(name, api_key)


def _text(value) -> str:
    """A prompt given as text, or as the path of a file holding it."""
    if isinstance(value, Path) or (isinstance(value, str) and "\n" not in value
                                   and value.endswith((".txt", ".md")) and Path(value).is_file()):
        return Path(value).read_text(encoding="utf-8")
    return str(value)


def _fields(value) -> list[dict]:
    """A schema given as a list of fields, a JSON file, or a pydantic model class."""
    if isinstance(value, (str, Path)):
        data = json.loads(Path(value).read_text(encoding="utf-8"))
        value = data["fields"] if isinstance(data, dict) else data
    if isinstance(value, type) and hasattr(value, "model_fields"):
        fields = []
        for name, info in value.model_fields.items():
            annotation = info.annotation
            base = next((t for t in getattr(annotation, "__args__", (annotation,))
                         if t in FIELD_TYPES), str)
            fields.append({"name": name, "type": FIELD_TYPES[base],
                           "description": info.description or ""})
        return fields
    fields = [dict(f) for f in value]
    for f in fields:
        if not f.get("name"):
            raise ValueError(f"A schema field needs a name: {f}")
        if f.setdefault("type", "string") not in FIELD_TYPES.values():
            raise ValueError(f"Field {f['name']}: type must be one of "
                             f"{', '.join(FIELD_TYPES.values())}, not {f['type']}.")
        f.setdefault("description", "")
    return fields
