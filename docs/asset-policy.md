# Asset Policy

Git tracks **how to reproduce a render**, not the rendered bytes.

## Tiers

| Location | Purpose | Git |
|---|---|---|
| `refs/` | Small inputs that define the look: reference frames, keyframes, LUTs, fonts, audio beds | Tracked, preferably Git LFS |
| `shared/` | Inputs intentionally shared across projects | Tracked, read-only, preferably Git LFS |
| `assets/` | Working media, intermediates, renders, proxies | Ignored |
| `deliverables/` | Final exports and variants | Ignored, external artifact store |
| `runs/` | Run manifests with hashes and parameters | Tracked for approved/final runs |
| `state/` | Cache, locks, logs, local run log | Ignored |

`MEDIA_ROOT` optionally moves `assets/` and `deliverables/` outside the repo:

```text
${MEDIA_ROOT}/<project>/assets/<shot>/<stage>/vNNN/
```

Logical paths in YAML stay stable (`assets/s010/keyframe/v001`); the runner
resolves them against `MEDIA_ROOT` when it is set.

## Git LFS vs external store

- **Small team, refs under a few GB:** Git LFS is enough. Install Git LFS
  before adding binary refs; if you do not use it, remove the LFS lines from
  `.gitattributes` first.
- **Large media, multiple machines, cloud:** use DVC + S3/MinIO or a
  content-addressed artifact store. Git tracks pointer files and manifests only.
- **Text-only repo:** acceptable only when the external store is backed up and
  every render manifest records input/output hashes.

Do not globally ignore `*.png` / `*.jpg`; that prevents tracked refs. Scope
ignores to `assets/`, `deliverables/`, and `state/`.

## Hashes

Every run manifest records:

- SHA-256 of each input file.
- SHA-256 of each output file.
- SHA-256 of the workflow file and a topology hash.
- Model id, hash (when available), license, and profile.
- Exact resolved parameters, including the actual seed.

Approvals reference a run id and, ideally, an output hash. A file that is not in
a manifest is not a deliverable.

## Retention

- Keep approved inputs and approved outputs for the life of the project.
- Prune intermediates after review; keep the manifests.
- Archive finished projects to cold storage; keep the repo and manifests.
- Never delete an approved/final run manifest.
- Never overwrite an existing version directory.

## Secrets

- `.env` is ignored. `.env.example` is tracked and contains placeholders only.
- Model licenses must be recorded. Unknown license means “stop before delivery.”
- Do not commit provider API keys, signed URLs, or private keys.
