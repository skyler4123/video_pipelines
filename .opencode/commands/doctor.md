---
description: Check the local pipeline environment
agent: build
---
Run `./vp doctor` and summarize:

- Python and dependency status,
- ffmpeg/ffprobe availability,
- git status,
- `MEDIA_ROOT` and `MODELS_DIR` configuration,
- ComfyUI reachability.

Do not change the environment unless the user asks.
