# Concepts

This is the canonical vocabulary for the workspace. `README.md` is the
quickstart, `docs/conventions.md` contains the rules, and this file explains how
the pieces fit together.

## Project

A project is an isolated production namespace under `projects/<project>/`.
It owns its brief, pipeline, shots, stage workflows, refs, assets, and run
manifests.

A project never reads from another project implicitly. Shared inputs belong in
the root `shared/` directory and require explicit approval.

## Shot

A shot is one creative unit in the final video, such as `s010` — “hero product
push-in.”

A shot defines:

- the prompt and negative prompt,
- the default profile and seed,
- per-stage model and parameter overrides,
- the per-stage output version.

The shot is the “what.” It is an instance of the project’s production pipeline.

## Pipeline

`pipeline.yaml` is the ordered list of stages for the project, plus the adapter,
model, workflow, dependencies, and enabled state of each stage.

The pipeline is the “route” a shot takes:

```text
keyframe → video → qc
```

It can also include upscale, interpolation, audio, assembly, and delivery stages
when those are implemented.

## Stage

A stage is one production step, such as `keyframe`, `video`, or `qc`.

Stages are reusable across shots. Adding a second shot does not duplicate the
ComfyUI graph; both shots use the same stage with different shot parameters.

A stage defines:

- its adapter (`comfyui`, `ffmpeg`, `diffusers`, `hosted_api`, or `mock`),
- its action (`generate`, `qc`, `assemble`, or `encode`),
- the workflow and parameter map, when needed,
- its default model,
- its dependencies,
- whether it is enabled.

## Workflow

`stages/<stage>/workflow.api.json` is the ComfyUI API-format graph for that
stage. The runner submits this graph to ComfyUI.

API format is different from the UI-format workflow you edit in the ComfyUI web
UI. The API graph is the execution contract; the UI graph is the editable source.
See `docs/comfyui.md`.

## Workflow map

`stages/<stage>/workflow.map.yaml` maps readable parameter names to stable
`_meta.title` values in the workflow.

```yaml
params:
  sampler.seed:
    node_title: SAMPLER
    input: seed
```

The runner changes only mapped inputs. It does not rewrite the graph topology.

## Shot overrides

`shot.yaml` can override stage defaults:

```yaml
stages:
  video:
    model: wan2.2-i2v-a14b
    output: assets/s010/video/v001
    params:
      video.frames: 49
```

A shot can also override `workflow` and `map` for an intentional one-off graph,
but that should be the exception.

## Assets and versions

Stage output paths are versioned:

```text
assets/<shot>/<stage>/vNNN
```

Examples:

```text
assets/s010/keyframe/v001
assets/s010/video/v001
```

The runner refuses to overwrite a non-empty output directory. Bump the version
in `shot.yaml` instead.

Working media lives in `assets/`, final exports in `deliverables/`, and small
tracked inputs in `refs/` or `shared/`. See `docs/asset-policy.md`.

## Run manifest

Every render writes `runs/<run_id>.yaml` and appends to the ignored
`state/runs.jsonl`.

The manifest records:

- stage, adapter, profile, and model,
- workflow and topology hashes,
- resolved parameters, including the actual seed,
- input and output hashes,
- QC results and errors.

Commit manifests for approved and final runs.

## How a shot is executed

1. `project.yaml` supplies project defaults.
2. `pipeline.yaml` defines the stage route.
3. `shot.yaml` selects the profile, seed, model, output version, and overrides.
4. `registry/models.yaml` supplies profile presets and constraints.
5. `stages/<stage>/workflow.map.yaml` injects values into the API graph.
6. The adapter executes the stage.
7. The runner writes a manifest with input/output hashes.

## The demo project

`projects/demo_01` currently contains:

| Stage | Status | What it does |
|---|---|---|
| `keyframe` | Real | Standard ComfyUI SDXL text-to-image graph |
| `video` | Placeholder | Disabled; contains a `Note` node, not a real image-to-video graph |
| `qc` | Implemented | Runs `ffprobe` against the dependent stage output |

Current implications:

- The keyframe stage is the only real generator.
- The video dependency is declared (`depends_on: [keyframe]`), but the video
  graph is not wired to load the keyframe yet.
- `qc` currently depends on `keyframe`, because `video` is disabled.
- `ffprobe` is not installed on the current workstation, so QC would be skipped
  until ffmpeg is installed.
- The demo keyframe needs `sd_xl_base_1.0.safetensors`, which is not currently
  installed in `~/ComfyUI/models/checkpoints/`.

To enable video:

1. Replace `stages/video/workflow.api.json` with an installed image-to-video
   graph.
2. Add a `LoadImage`-style node that consumes the keyframe input.
3. Fill in `stages/video/workflow.map.yaml`.
4. Enable the stage in `pipeline.yaml`.
5. Change `qc.depends_on` to `[video]`.
6. Update the shot QC target resolution.
7. Run `./vp validate`, `./vp plan demo_01/s010`, then render.

## Implementation status

| Capability | Status |
|---|---|
| Project/shot namespaces | Implemented |
| Stage pipeline and dependencies | Implemented |
| Validation and planning | Implemented |
| ComfyUI adapter | Implemented |
| ffmpeg QC | Implemented, requires `ffprobe` |
| Run manifests and hashes | Implemented |
| ComfyUI launcher | Implemented |
| Image-to-video demo graph | Placeholder only |
| Upscale/interpolation/audio | Not implemented |
| Assembly and delivery | Not implemented |
| Diffusers and hosted API adapters | Stubs |
| Distributed queue / multi-GPU scheduler | Not implemented |
| Verified model hashes and licenses | Placeholders |
