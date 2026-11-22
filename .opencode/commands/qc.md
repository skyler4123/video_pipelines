---
description: Run QC for a rendered shot
agent: build
---
Run QC for `$1`.

1. Run `./vp plan $1 --stage qc --json` and show the expected checks.
2. If the QC stage is enabled, run `./vp render $1 --stage qc --yes`.
3. Report the manifest path, every probe result, and every mismatch.

Do not change the source workflow or overwrite media.
