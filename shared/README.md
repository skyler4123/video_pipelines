# Shared Inputs

Cross-project inputs live here only when more than one project genuinely needs
them. Treat this directory as read-only by default.

Rules:

- Reference shared files explicitly from `shot.yaml` as `shared/<path>`.
- Use Git LFS for binary files.
- Record a hash in the run manifest like any other input.
- Do not put working renders, intermediates, or deliverables here.
- A project must not mutate a shared file; copy it into the project `refs/`
  first if a project-specific variant is needed.
