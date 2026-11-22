# Conventions

## Namespace contract

- Project id: `^[a-z][a-z0-9_]{2,31}$`. Lowercase, immutable, used in every path.
- Shot id: `^[a-z][a-z0-9_]{1,31}$`, for example `s010`.
- Stage id: `^[a-z][a-z0-9_]{1,31}$`, for example `keyframe`, `video`, `qc`.
- Version: `v001`, `v002`, … Versions only increase and are never reused.
- Stage output path: `assets/<shot>/<stage>/vNNN`. Final delivery copies live in
  `deliverables/` and are recorded in a delivery manifest.
- ComfyUI output prefix: `<project>/<shot>/<stage>/vNNN`.
- Git delivery tag: `<project>-vNNN`, for example `demo_01-v001`.

No cross-project references. Shared inputs belong in `shared/` and require
explicit approval and a recorded hash.

## Project layout

```text
projects/<project>/
├── project.yaml          # brief, owner, defaults, variants
├── pipeline.yaml         # stages and adapters
├── AGENTS.md             # project-specific rules
├── README.md
├── shots/
│   └── s010/
│       ├── shot.yaml     # source of truth
│       └── notes.md      # human notes
├── stages/
│   ├── keyframe/
│   │   ├── workflow.api.json
│   │   └── workflow.map.yaml
│   └── video/
│       ├── workflow.api.json
│       └── workflow.map.yaml
├── refs/                 # small tracked inputs, LFS
├── runs/                 # committed run manifests
├── assets/               # ignored working media
├── deliverables/         # ignored final exports
└── state/                # ignored cache, locks, logs
```

## Shot lifecycle

Creative status in `shot.yaml`:

`draft → in_review → approved → final → archived`

Render state lives in run manifests, not in the creative status. A shot can be
`approved` only when it has an approval record that points to a successful run
manifest and, when set, a matching output hash.

## Versions

- Bump the version whenever the prompt, seed, model, workflow, or parameters change.
- Never overwrite an existing version. The runner refuses non-empty output directories.
- Use fixed seeds for approved work. Exploratory runs may use random seeds, but the
  actual seed must be recorded in the manifest.
- Keep the latest approved run id in `approvals`; do not use “latest file” logic.

## Git

- `main` is the integration branch.
- Feature branches: `proj/<project>/<shot>-<topic>`.
- Commit messages: `<project>(<shot>): <change>` or `registry: <change>`.
- Tag delivery milestones only: `<project>-vNNN`.
- Track the recipe, not the bytes. See `docs/asset-policy.md`.
- Add `CODEOWNERS` when more than one person edits a project.

## Adding a stage

1. Add the stage to `pipeline.yaml`.
2. Add the workflow and map under `stages/<stage>/`.
3. Add per-stage output and params to affected `shot.yaml` files.
4. Add the adapter to `registry/tools.yaml`.
5. Run `./vp validate` and `./vp plan <project>/<shot>`.

## Adding a model

1. Add an entry to `registry/models.yaml` with a pinned hash and license.
2. Add `animatic`, `preview`, and `final` presets, or rely on `registry/presets.yaml`.
3. Add constraints such as `frames: "4n+1"` and resolution multiples.
4. Reference it from a stage or a shot override.
5. Run `./vp validate`.

## Definition of done

- `./vp validate` passes.
- `./vp plan <project>/<shot>` resolves without errors.
- The render manifest exists and has output hashes.
- QC passes for the target specification.
- The approval record references the manifest and hash.
- The project README and `notes.md` reflect any creative decisions.
