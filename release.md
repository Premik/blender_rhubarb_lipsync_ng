# Release

## Bump the version

- Set `[project].version` in `pyproject.toml`.
- If upgrading the bundled Rhubarb CLI, also update `[tool.rhubarb_lipsync.download].version` and each platform's `download_sha256`.

## Build the release zips

The scripts work with plain system python (no conda):

```sh
python scripts/rhubarb_bin.py   # download + checksum-verify Rhubarb binaries
python scripts/package.py       # propagate the version, zip dist/ per platform
```

This updates the version in `__init__.py`, `misc_operators.py`, `blender_manifest.toml`, `README.md` and `sphinx/conf.py`, and creates `dist/rhubarb_lipsync_ng-<Platform>-<version>.zip`.

## Run the tests

```sh
conda run -n rhubarb pytest -n auto --forked            # needs the conda env (bpy)
python scripts/compatibility_tests.py --update-readme  # installs the dist zip into real Blender versions
```

- Compatibility test options: `-n all` tests all Blender versions, `-r` refreshes the cached Blender release listings.
- `--update-readme` rewrites the *Supported Blender versions* table in `README.md`.

## Build the docs

Only needed when at least the **minor** version changes — skip for bugfix releases. Requires `rinohtype` (PDF builder), which is not installed system-wide; use the conda env that has it:

```sh
conda run -n rhubarb python scripts/sphinx_build.py
```

Creates `dist/rhubarb-lipsync-docs-<major.minor>.zip`. (The release workflow builds it on every tag push anyway.)

## Commit, tag and push

The tag must match the `pyproject.toml` version:

```sh
git commit -am "Release vX.Y.Z"
git tag vX.Y.Z
git push && git push --tags
```

## Publish the GitHub release

- Pushing the `v*.*.*` tag triggers `.github/workflows/release.yml`, which creates a **draft** release with the `dist/*.zip` files attached (3 platform zips + docs zip).
- Fill in the release notes and publish the draft on GitHub.
- Optionally regenerate `release_notes.md` afterwards (needs `~/github-token.txt`, run from repo root):

  ```sh
  python scripts/github_releases.py
  ```

## Update Superhive/Blender Market — TBD

TBD: automate with playwright. Draft checklist:

- Blender versions compatibility is flagged properly.
- Versions are organized in folders per platform.
- Shop readme is in sync with `README.md`.
- Release notes for the new version are added.
- Brief documentation is updated.
