---
description: Render one stage after showing the resolved plan
agent: build
---
Prepare a render for `$1`, stage `$2`.

If `$2` is empty, ask the user which stage to render before doing anything else.

1. Run `./vp plan $1 --stage $2 --json`.
2. Show the model, profile, adapter, output path, inputs, and resolved params.
3. Ask the user to confirm.
4. Only after explicit confirmation, run:
   `./vp render $1 --stage $2 --yes`
5. Report the manifest path and status.

Never render the `final` profile without explicit approval. Never overwrite an
existing version. If a version exists, propose a new version and wait.
