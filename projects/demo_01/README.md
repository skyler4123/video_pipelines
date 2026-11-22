# Demo Product Teaser

Project id: `demo_01`

This is the worked example for the workspace. It is a scaffold, not a finished
advertisement.

## Start

```bash
./vp validate projects/demo_01
./vp plan demo_01/s010
./vp render demo_01/s010 --stage keyframe
```

## What is real

- The keyframe stage uses a standard ComfyUI SDXL API graph.
- The model checkpoint name and presets are examples and must match your local
  installation.
- The video stage is disabled and contains a `Note` placeholder.

## First edits

- `project.yaml` — brief, owner, variants.
- `pipeline.yaml` — stage graph and adapters.
- `shots/s010/shot.yaml` — prompt, seed, profile, per-stage outputs.
- `stages/keyframe/workflow.api.json` — ComfyUI API-format graph.
- `stages/keyframe/workflow.map.yaml` — stable parameter mapping.

Before enabling the video stage, replace its workflow, map, and model entry, then
run `./vp validate` and `./vp plan demo_01/s010`. Also change the `qc` stage's
`depends_on` to `[video]` and update the shot QC target resolution.
