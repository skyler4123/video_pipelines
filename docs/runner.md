# Runner CLI

The runner is a small Python control plane. It does not install models or custom
nodes, and it does not edit ComfyUI graphs.

```bash
./vp doctor
./vp validate
./vp plan demo_01/s010
./vp render demo_01/s010 --stage keyframe
./vp render demo_01/s010 --stage qc --yes
```

## Commands

| Command | Purpose |
|---|---|
| `doctor` | Check Python, dependencies, ffmpeg, git, and ComfyUI reachability |
| `validate [target]` | Schema, namespace, workflow, media, secret, and approval checks |
| `plan target` | Resolve presets, params, inputs, outputs, and workflow mappings without rendering |
| `render target --stage id` | Render one stage and write a run manifest |
| `render target --all --yes` | Render all enabled stages in order |
| `new-project id --title ...` | Copy the project template |
| `new-shot project id --title ...` | Copy the shot template |
| `schemas` | Regenerate JSON schemas from the Pydantic models |
| `list` | List projects, shots, statuses, and stages |

`target` is `project/shot`, for example `demo_01/s010`.

## Plan before render

`plan` is cheap and catches most mistakes:

```bash
./vp plan demo_01/s010 --json
./vp render demo_01/s010 --stage keyframe --dry-run
```

It resolves:

- the model preset for the selected profile,
- shot stage overrides,
- prompt and seed,
- the versioned output path,
- inputs from earlier stages,
- workflow map injection,
- model constraints such as `4n+1` frames.

## Run manifests

Every render writes `projects/<project>/runs/<run_id>.yaml` and appends a line
to the ignored `state/runs.jsonl`.

A manifest contains the stage, profile, adapter, model, workflow hashes,
resolved parameters, input/output hashes, QC results, warnings, and errors.
Commit manifests for approved/final runs.

## Exit codes

- `0`: success or skipped (for example, ffprobe unavailable)
- `1`: validation/render failure
- `130`: interrupted

Set `VP_DEBUG=1` to see a traceback for unexpected errors.
