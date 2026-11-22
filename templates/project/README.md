# __PROJECT_TITLE__

Project id: `__PROJECT_ID__`

## Start

```bash
./vp validate projects/__PROJECT_ID__
./vp plan __PROJECT_ID__/s010
```

## First edits

- `project.yaml` — brief, owner, variants.
- `pipeline.yaml` — stage graph and adapters.
- `shots/s010/shot.yaml` — prompt, seed, profile, per-stage outputs.
- `stages/keyframe/workflow.api.json` — ComfyUI API-format graph.
- `stages/keyframe/workflow.map.yaml` — stable parameter mapping.

The `video` stage is disabled and contains a placeholder workflow. Replace it
with a graph that matches your installed models and custom nodes before enabling
it. If you enable it, update the `qc` stage's `depends_on` to `[video]` and
update the shot QC target resolution.
