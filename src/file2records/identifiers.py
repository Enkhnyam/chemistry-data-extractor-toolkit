"""Identifiers for extracted names: "zinc acetate" in a solvent column gets CHEBI:62984 next to
it, so a dataset can be joined with others that name the same compound differently.

Names are looked up in EBI's Ontology Lookup Service (OLS) rather than in an ontology loaded on
this computer. Loading ChEBI locally (pyobo with gilda, as first proposed in PR #6) needed more
than 6 GB of memory the first time, which a laptop with a browser open does not have; a lookup
is a quarter of a second and needs nothing installed. Every answer, including "no match", is
kept in the project's config/identifiers.json, so each name is looked up once, and an export
works offline once its names have been seen.

Abbreviations are the hard part: papers write "EG", and in ChEBI "EG" is the dipeptide Glu-Gly.
So the extraction also asks the model for every name each value goes by (see extraction.py),
and they are tried in order until one is in the ontology. A value of one or two characters is
never looked up as written: a blank is better than a confident wrong identifier.

Which fields get identifiers, and from which ontology, is a project setting:
{"solvent": "chebi", "catalyst": "chebi"}. Any ontology OLS serves works; ChEBI is the one the
browser offers.
"""
from concurrent.futures import ThreadPoolExecutor

import httpx

from . import config, storage
from .storage import read_json, write_json

OLS_SEARCH = "https://www.ebi.ac.uk/ols4/api/search"
ONTOLOGIES = {"chebi": "ChEBI: chemicals"}      # offered in the browser; Python takes any OLS id
TERM_URL = "https://bioregistry.io/{}"           # resolves an id from any ontology to its page
UNREACHABLE = object()                           # OLS didn't answer, which is not "no match"


def cache_file():
    return storage.CONFIG / "identifiers.json"


def chosen() -> dict[str, str]:
    """{field: ontology} for the text fields of the current schema that should get identifiers.
    A field since removed or changed to a number is left out."""
    names = {f["name"] for f in config.get_schema() if f.get("type", "string") == "string"}
    return {field: onto for field, onto in config.get_settings().get("identifiers", {}).items()
            if field in names and onto}


def lookup(name: str, ontology: str) -> dict | None:
    """{"id", "name"} of the term whose name or synonym is exactly `name`, or None. Raises
    httpx.HTTPError when OLS can't be reached, so that is never mistaken for "no match"."""
    response = httpx.get(OLS_SEARCH, timeout=httpx.Timeout(20, connect=5), params={
        "q": name, "ontology": ontology, "exact": "true", "rows": 25,
        "fieldList": "obo_id,label,synonym,is_obsolete"})
    response.raise_for_status()
    wanted = name.casefold()
    matches = []
    for term in response.json()["response"]["docs"]:
        names = [term.get("label", "")] + term.get("synonym", [])
        if term.get("is_obsolete") or wanted not in (n.casefold() for n in names):
            continue
        # Chemical symbols are case-sensitive -- "Ni" is nickel, "NI" a dipeptide -- so a match
        # in the same case wins, then the term's own name over a synonym, then the plainer name.
        label = term.get("label", "")
        matches.append(((name not in names, label.casefold() != wanted, len(label)),
                        {"id": term["obo_id"], "name": label}))
    return min(matches, key=lambda m: m[0])[1] if matches else None


def find(pairs) -> dict:
    """Look up every (ontology, name) not seen before, eight at a time, and remember the
    answers. Returns the whole cache: {ontology: {name: {"id", "name"} or None}}. A name OLS
    couldn't be asked about is left out, so it is tried again next time."""
    cache = read_json(cache_file(), {})
    todo = sorted({(o, n) for o, n in pairs if n not in cache.get(o, {})})
    if not todo:
        return cache

    def ask(pair):
        try:
            return pair, lookup(pair[1], pair[0])
        except (httpx.HTTPError, ValueError, KeyError):
            return pair, UNREACHABLE

    with ThreadPoolExecutor(8) as pool:
        for (ontology, name), found in pool.map(ask, todo):
            if found is not UNREACHABLE:
                cache.setdefault(ontology, {})[name] = found
    write_json(cache_file(), cache)
    return cache


def candidates(record: dict, field: str, synonyms: dict) -> list[str]:
    """The names to look a record's value up by, best first: the synonyms the model gave for
    it, then the value as written. A name of one or two characters is never looked up."""
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        return []
    value = value.strip()
    names = synonyms.get(field, {}).get(value, []) + [value]
    return [n for n in dict.fromkeys(names) if len(n) > 2]


def for_records(records: list[dict], synonyms: dict | list[dict] | None = None) -> list[dict]:
    """For each record, {field: {"id", "name", "url"}} for the values that have an identifier.

    `synonyms` is the {field: {value: [names]}} the model gave with a paper's records, or a list
    of those, one per record, for records from several papers. Looks up names not seen before;
    never raises, because an identifier is a bonus and the records are the point."""
    fields = chosen()
    if not fields or not records:
        return [{} for _ in records]
    per_record = synonyms if isinstance(synonyms, list) else [synonyms or {}] * len(records)
    names = [{field: candidates(record, field, known) for field in fields}
             for record, known in zip(records, per_record)]
    try:
        cache = find({(fields[f], n) for found in names for f, ns in found.items() for n in ns})
    except OSError:
        cache = read_json(cache_file(), {})
    result = []
    for found in names:
        terms = {}
        for field, tried in found.items():
            term = next((t for n in tried if (t := cache.get(fields[field], {}).get(n))), None)
            if term:
                terms[field] = {**term, "url": TERM_URL.format(term["id"])}
        result.append(terms)
    return result
