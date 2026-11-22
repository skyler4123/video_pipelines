# Video Pipelines

A Git-tracked control plane for multi-project, multi-model, multi-tool video
production.

- **Namespaces:** every project lives under `projects/<project>/` and is isolated.
- **Stages:** keyframe, video, upscale, QC, assembly, and delivery are separate
  steps with their own tool, model, workflow, and output.
- **Recipes, not bytes:** Git tracks YAML, API-format ComfyUI workflows, schemas,
  registries, and run manifests. Media lives in `assets/` or an external store.
- **Reproducibility:** pinned models/tools, fixed seeds, hashed inputs/outputs,
  and a run manifest for every render.
- **Flexible tools:** ComfyUI, diffusers, ffmpeg, and hosted APIs sit behind
  adapters. Adding a tool does not require rewriting every shot.

## Quickstart

Requirements: Python 3.10+, PyYAML, pydantic. Optional: git-lfs, ffmpeg.

```bash
python3 -m pip install -r requirements.txt
./vp doctor
./vp validate
./vp plan demo_01/s010
```

The demo project is a scaffold. Its keyframe stage is a real ComfyUI API graph;
the video stage is disabled and contains a placeholder. Replace the workflow and
model names with what is installed on your ComfyUI machine.

## Common commands

```bash
./vp list
./vp validate demo_01/s010
./vp plan demo_01/s010 --json
./vp render demo_01/s010 --stage keyframe
./vp render demo_01/s010 --stage qc --yes
./vp new-project spring_campaign --title "Spring Campaign"
./vp new-shot spring_campaign s020 --title "Product close-up"
./vp schemas
```

`render` refuses to overwrite a non-empty version directory. Bump
`assets/<shot>/<stage>/v001` to `v002` in `shot.yaml` instead.

## Layout

```text
video_pipelines/
├── AGENTS.md                 # global agent rules
├── opencode.json             # OpenCode permissions
├── .gitattributes            # LFS and line-ending rules
├── .gitignore
├── .env.example
├── vp                        # CLI wrapper
├── docs/
│   ├── conventions.md
│   ├── asset-policy.md
│   ├── comfyui.md
│   └── runner.md
├── schemas/                  # generated JSON schemas
├── registry/
│   ├── models.yaml           # model ids, hashes, licenses, constraints, presets
│   ├── tools.yaml            # ComfyUI/diffusers/ffmpeg adapters
│   ├── presets.yaml          # profile fallbacks
│   └── comfyui-nodes.lock    # custom-node pins
├── runner/                   # CLI, planner, validator, adapters
├── templates/                # new-project / new-shot scaffolds
├── shared/                   # cross-project inputs, read-only by default
└── projects/
    └── demo_01/
        ├── project.yaml
        ├── pipeline.yaml
        ├── AGENTS.md
        ├── shots/s010/{shot.yaml,notes.md}
        ├── stages/{keyframe,video}/...
        ├── refs/
        ├── runs/
        ├── assets/           # ignored
        ├── deliverables/     # ignored
        └── state/            # ignored
```

## How a shot is resolved

1. `project.yaml` supplies defaults.
2. `pipeline.yaml` defines the stage order and adapters.
3. `shot.yaml` selects the profile, seed, per-stage model, output version, and
   sparse parameter overrides.
4. `registry/models.yaml` supplies the profile preset and constraints.
5. `stages/<stage>/workflow.map.yaml` injects parameters into the
   API-format ComfyUI graph by stable node title.
6. The runner writes a manifest with input/output hashes.

## ComfyUI setup

1. Set `COMFYUI_URL` (default `http://127.0.0.1:8188`).
2. Put the exact checkpoint filename in the model preset or shot params.
3. Export the workflow in **API format** to
   `projects/<project>/stages/<stage>/workflow.api.json`.
4. Give mapped nodes stable `_meta.title` values and update
   `workflow.map.yaml`.
5. Run `./vp plan <project>/<shot>` to verify parameter injection.
6. Run `./vp render <project>/<shot> --stage <stage>`.

See `docs/comfyui.md` for details.

## Multi-model and multi-tool

A stage declares an adapter:

```yaml
stages:
  - id: keyframe
    adapter: comfyui
    workflow: stages/keyframe/workflow.api.json
    map: stages/keyframe/workflow.map.yaml
    model: sdxl-base-1.0

  - id: video
    adapter: comfyui
    workflow: stages/video/workflow.api.json
    map: stages/video/workflow.map.yaml
    model: wan2.2-i2v-a14b
    depends_on: [keyframe]

  - id: qc
    adapter: ffmpeg
    action: qc
    depends_on: [video]
```

Supported adapter names: `comfyui`, `ffmpeg`, `mock` (test-only), `diffusers`
(stub), `hosted_api` (stub). Add new behavior in `runner/adapters/`, not in every
shot file.

## Git and assets

- Track: `project.yaml`, `pipeline.yaml`, `shot.yaml`, stage workflows/maps,
  registries, schemas, runner, docs, run manifests.
- Ignore: `assets/`, `deliverables/`, `state/`, model weights, renders, secrets.
- `refs/` is for small tracked inputs; enable Git LFS before adding larger files.
- For larger productions, set `MEDIA_ROOT` to an external volume and/or use
  DVC + S3/MinIO.
- Never commit model weights or final videos.

See `docs/asset-policy.md`.

## OpenCode

- `AGENTS.md` contains the global rules. Each project has its own `AGENTS.md`
  with project-specific notes; OpenCode loads it when working in that directory.
- `.opencode/commands/` contains `/new-project`, `/new-shot`, `/validate`,
  `/plan-render`, `/render`, `/qc`, and `/doctor`.
- `opencode.json` blocks edits to `assets/`, `deliverables/`, `state/`, `models/`,
  and `.env`, asks before shell commands, and denies `git push`.

## Current limitations

- The `video` stage in the template/demo is disabled and uses a placeholder
  workflow. Replace it with a graph that matches your installed nodes.
- The `diffusers` and `hosted_api` adapters are stubs.
- The ffmpeg adapter implements QC only; assembly/encode is a stub.
- Model hashes and licenses in `registry/models.yaml` are placeholders and must
  be verified before commercial delivery.
