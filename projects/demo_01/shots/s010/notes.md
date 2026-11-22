# Shot s010 — Hero product push-in

## Intent

A short product teaser. Start with a clean hero keyframe, then attempt a subtle
camera push-in once the video stage is configured.

## Notes

- The keyframe stage uses the standard SDXL graph and the `animatic` profile.
- The video stage is disabled. Replace
  `stages/video/workflow.api.json` and its map before enabling it. If you enable
  it, update the `qc` stage dependency and QC resolution.
- The first render should focus on composition and lighting, not motion.
- Bump the output version when the prompt, seed, model, or workflow changes.
