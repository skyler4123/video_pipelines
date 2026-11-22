---
description: Scaffold a new shot inside a project
agent: build
---
Create shot `$2` in project `$1` with title `$3`.

1. Read `projects/$1/AGENTS.md` and `docs/conventions.md`.
2. Run `./vp new-shot $1 $2 --title "$3"`.
3. Edit `projects/$1/shots/$2/shot.yaml` only as needed for the requested shot.
4. Run `./vp validate $1/$2`.
5. Report the created files and any warnings.

Do not render or create media.
