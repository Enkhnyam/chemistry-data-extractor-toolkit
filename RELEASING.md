# Releasing file2records

## Once: let GitHub publish to PyPI

1. Sign in at <https://pypi.org> (create an account, with two-factor authentication, if needed).
2. Go to **Your projects → Publishing → Add a new pending publisher** and enter:
   - PyPI project name: `file2records`
   - Owner: `Enkhnyam`
   - Repository: `chemistry-data-extractor-toolkit`
   - Workflow: `publish.yml`
   - Environment: `pypi`
3. On GitHub: **Settings → Environments → New environment**, named `pypi`. Optionally require
   your own approval before it runs.

No token is created or stored: PyPI trusts that one workflow in that one repository.

## Every release

1. Set the version in `pyproject.toml`, `src/file2records/__init__.py` and `CITATION.cff`.
2. Run the tests and build locally:

   ```bash
   uv run python -m unittest discover -s tests
   rm -rf dist && uv build && uvx twine check --strict dist/*
   ```

3. Commit, push, and on GitHub **Releases → Draft a new release** with tag `vX.Y.Z` (it must
   match the version). Publishing the release runs `publish.yml`, which uploads to PyPI.

A version number can be uploaded to PyPI only once, ever — a mistake is fixed by releasing the
next version, not by re-uploading.

## Without GitHub Actions

With an API token from <https://pypi.org/manage/account/token/>:

```bash
rm -rf dist && uv build
uvx twine upload dist/*            # username: __token__, password: the token
```

To rehearse first, upload to TestPyPI (a separate account at <https://test.pypi.org>):

```bash
uvx twine upload --repository testpypi dist/*
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ file2records
```
