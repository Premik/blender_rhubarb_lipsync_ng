# Release

## Bump the version

- Set `[project].version` in `pyproject.toml`.
- Update `release_notes.md` with the new version's notes (the tag workflow embeds it into the docs on every release).
- If upgrading the bundled Rhubarb CLI, also update `[tool.rhubarb_lipsync.download].version` and each platform's `download_sha256`.

## Format the code

Run isort and ruff autofixes before building the zips:

```sh
isort rhubarb_lipsync tests scripts
conda run -n rhubarb ruff check --fix rhubarb_lipsync tests scripts
```

`isort` is installed system-wide, `ruff` only in the `rhubarb` conda env.

## Build the release zips

The scripts work with plain system python (no conda):

```sh
python scripts/package.py       # download + checksum-verify binaries, propagate version, zip dist/ per platform
```

`package.py` is self-sufficient: it downloads and checksum-verifies the Rhubarb binaries, swaps the binary for each platform in `bin/` while zipping, and restores the previously deployed platform afterwards. (`python scripts/rhubarb_bin.py` is still available for downloading/preparing all binaries standalone.)

This updates the version in `__init__.py`, `misc_operators.py`, `blender_manifest.toml`, `README.md` and `sphinx/conf.py`, and creates `dist/rhubarb_lipsync_ng-<Platform>-<version>.zip`.

Pass a platform name substring (e.g. `python scripts/package.py Windows`) to build only that platform; an unknown name fails instead of building nothing.

`package.py` fails if `dist/` contains addon zips that are not part of this release (another version or an unknown platform). Remove or move them away manually before packaging.

## Run the tests

```sh
conda run -n rhubarb pytest -n auto --forked            # needs the conda env (bpy)
python scripts/compatibility_tests.py --update-readme  # installs the dist zip into real Blender versions
```

- Compatibility test options: `-n all` tests all Blender versions, `-r` refreshes the cached Blender release listings.
- `--update-readme` rewrites the *Supported Blender versions* table in `README.md`.
- The compatibility tests cache Blender release pages and downloaded installers in `/extra/temp/blenderInstall/` (~13 GB, superseded archives included). **Never purge this directory** — not as release cleanup, not to free space: it is the download cache the compat suite depends on, and wiping it forces a full re-download of every Blender version.

## Build the docs

Only needed when at least the **minor** version changes — skip for bugfix releases. Requires `rinohtype` (PDF builder), which is not installed system-wide; use the conda env that has it:

```sh
conda run -n rhubarb python scripts/sphinx_build.py
```

Creates `dist/rhubarb-lipsync-docs-<major.minor>.zip`. (The release workflow builds it on every tag push anyway.) Like `package.py`, it fails if `dist/` contains a docs zip of another major.minor version.

## Commit, tag and push

The tag must match the `pyproject.toml` version:

```sh
git commit -am "Release vX.Y.Z"
git tag vX.Y.Z
git push && git push --tags
```

## Publish the GitHub release

- Pushing the `v*.*.*` tag triggers `.github/workflows/release.yml`, which verifies that `dist/` contains exactly the expected zips (3 platform addon zips + 1 docs zip) and creates a **draft** release with them attached.
- Fill in the release notes and publish the draft on GitHub.
- Optionally regenerate `release_notes.md` from the published releases afterwards (post-publish only; it cannot supply notes for a release that does not exist yet; needs `~/github-token.txt`, run from repo root):

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
