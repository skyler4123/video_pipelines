# Shot __SHOT_ID__

Replace with blocking notes, references, and review feedback.

- Keep the prompt in `shot.yaml`; this file is for human notes.
- Never reuse an output version. Bump `v001` to `v002` when changing inputs,
  workflow, model, or parameters.
- Record approval by adding an entry under `approvals` in `shot.yaml` only after
  a successful run manifest exists.
