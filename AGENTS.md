# Video Pipelines — Agent Rules

## Isolation

- `projects/<id>/` is an isolated namespace. Do not read or write another project unless the user explicitly asks.
- Read `project.yaml`, `pipeline.yaml`, and the project `AGENTS.md` before working.
- `shot.yaml` is the source of truth; `notes.md` is prose.
- IDs are immutable. Never renumber a shot or reuse a version.

## Assets

- Media lives in `assets/` and is git-ignored. Do not scan or list it; open only explicit paths from `shot.yaml` or paths the user provides.
- Never commit media, model weights, renders, or secrets.
- Use `${MEDIA_ROOT}` and `${MODELS_DIR}`; no absolute machine paths.
- `refs/` is only for small tracked inputs (LFS or external store).
- Never delete or overwrite approved/final media.

## Workflows

- Committed workflows must be API-format, valid JSON.
- Change parameters through `shot.yaml` stage params and `workflow.map.yaml`.
  Do not hand-edit node graphs unless the user explicitly asks.
- Preserve node topology. Never auto-install custom nodes or use unknown node classes.
- Prefer stable `_meta.title` values over numeric node IDs.
- Run `./vp validate <project>[/<shot>]` after every change.

## Rendering

- Profiles: `animatic | preview | final`; resolve from `registry/models.yaml`.
- ComfyUI runs outside this repo; start it with `bin/comfy` only when the user asks.
- Use fixed seeds for approved work; record the actual seed in the run manifest.
- Ask before final/upscale/interpolation or jobs longer than 10 minutes.
- One job per GPU. Never overwrite an existing version.
- Every render goes through `./vp render` and writes a run manifest.

## Stop conditions

- Unknown model, version, license, or missing input → stop and ask.
- Ambiguous shot or failed QC → stop and ask.
- Do not modify `schemas/*.json` by hand; run `./vp schemas`.

## Verification

```bash
./vp validate
./vp plan <project>/<shot>
./vp render <project>/<shot> --stage <stage> --dry-run
```
