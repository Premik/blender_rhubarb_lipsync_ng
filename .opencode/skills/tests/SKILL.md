---
name: tests
description: How to run test/verifications of this repo
---

All tests are pytest-based and live in `tests/` (run from the repo root — pyproject sets
`pythonpath = [".", "tests"]`). They import `bpy` (Blender as python module), which only
exists in the `rhubarb` conda env — a bare `pytest` with the system python fails on
imports. bpy keeps global state, so tests are isolated per process via `pytest-xdist` +
`pytest-forked` (both already installed in the env):

```sh
conda run -n rhubarb pytest -n auto --forked
```

For quicker iteration on a single file/test, the fork/parallel flags can be dropped:
`conda run -n rhubarb pytest tests/test_capture.py -k some_test`.
The full suite can take a while — running it via a subagent keeps this session free.

Give the agent (or keep in mind when running yourself) following additional instruction:

```
Read @tests/readme.md for generic test instructions.
- Analyze the output and find details about the failures/errors.
- Output which test(s) has failed from which file.
- Deduplicate the errors. If likely same cause triggered multiple failures, only output 1x.
- Compact the stack traces, only include the important lines of the stack, but keep line numbers and files in.
- Don't try to solve/fix the issues but report them. You can do light analysis but don't go too deep.
```

Should you need more knowledge about tests in general or troubleshoot failed tests, also
read the @tests/readme.md, unless it is already in your context.
But don't read this readme in advance just for the case.

Separately from the pytest suite, `scripts/compatibility_tests.py` runs the `tests/`
suite inside real Blender installations — it downloads and installs several Blender
versions, so it is slow and network-heavy. **Never run it by default; only when the
user explicitly asks for compatibility tests.**

When asked to run them without further qualifiers, use the defaults — the 2 newest
Blender versions, no cache refresh:

```sh
conda run -n rhubarb python scripts/compatibility_tests.py
```

- `-n/--count N` — how many newest versions to test; `all`/`-1` = all, `0` = none.
- `-r/--refresh [MIN_MAJOR]` — drop cached Blender release pages for majors >=
  MIN_MAJOR (default 4) before running. Refresh **only** when the user explicitly
  asks for it, never as part of a default run.

After a compatibility test run **has been executed** (and only then — not for
`-n 0` or skipped runs), update the `### Supported Blender versions` table in
`README.md` with the new results: refresh the point-release numbers, counts, and
✔️/❌ status per tested version, and add rows for any newly discovered versions.
Leave untested versions' rows as they are. Do **not** update this table from cache
scraping or version listings alone — only from actual test results.

$ARGUMENTS
