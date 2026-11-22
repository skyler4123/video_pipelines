---
description: Scaffold a new isolated project namespace
agent: build
---
Create a project named `$1` with title `$2`.

1. Read `docs/conventions.md` first.
2. Run `./vp new-project $1 --title "$2"`.
3. Run `./vp validate projects/$1`.
4. Report the files created and any validation warnings.

Do not render, download models, or create media.
