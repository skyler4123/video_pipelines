# ComfyUI Workflows

## API format, not UI format

The runner submits workflows to ComfyUI's `/prompt` endpoint. Store the
**API-format** JSON as `*.api.json`.

A UI-format export can be kept for visual editing, but it is not the execution
contract. If you keep both, name them explicitly:

```text
workflow.ui.json    # source for humans, if needed
workflow.api.json   # committed execution contract
```

## Stable node titles

Numeric node ids change when a graph is rerouted. Give every mapped node a
stable `_meta.title`:

```json
"27": {
  "class_type": "KSampler",
  "inputs": { "...": "..." },
  "_meta": { "title": "SAMPLER" }
}
```

Map parameters by title:

```yaml
# stages/video/workflow.map.yaml
schema: 1
params:
  sampler.seed:
    node_title: SAMPLER
    input: seed
  video.frames:
    node_title: VIDEO_LENGTH
    input: length
```

`shot.yaml` then holds only the values:

```yaml
stages:
  video:
    params:
      sampler.seed: 123456
      video.frames: 49
```

## What the runner changes

Only values listed in `workflow.map.yaml`. It preserves:

- node ids,
- links and graph topology,
- unknown inputs and `_meta`,
- the rest of the workflow file.

A topology hash is recorded in the run manifest. If the graph changes, the hash
changes and the run is no longer comparable to an earlier approval.

## Paths

Never commit absolute paths. Use project-relative paths:

- inputs: `refs/...` or the previous stage output;
- outputs: `assets/<shot>/<stage>/vNNN`;
- runtime model roots: `${MODELS_DIR}`.

The ComfyUI adapter downloads returned files into the stage output directory and
records them in the manifest. ComfyUI's own `filename_prefix` is set from the
stage output, but the adapter does not trust node-supplied machine paths.

## Custom nodes and models

- Pin custom-node repositories and commits in `registry/comfyui-nodes.lock`.
- Pin the ComfyUI image digest in `registry/tools.yaml`.
- Do not auto-install nodes from a workflow JSON.
- Do not download models automatically. Missing model = stop and ask.
- Record model license and hash in `registry/models.yaml`.

## Troubleshooting

- `cannot reach ComfyUI`: start ComfyUI or set `COMFYUI_URL`.
- `ComfyUI rejected the workflow`: the response contains `node_errors`; check
  node class availability and input names.
- `workflow map ... node title not found`: the graph was edited or the title was
  renamed. Update the map and review the topology hash change.
- `missing required parameter`: add the value to the preset in
  `registry/models.yaml` or to `shot.yaml` stage params.
