# Schemas

These JSON Schemas are generated from the Pydantic models in `runner/models.py`.
Do not edit them by hand.

```bash
./vp schemas
```

Use them in your editor or CI to validate `project.yaml`, `pipeline.yaml`,
`shot.yaml`, and workflow maps. The registry schemas describe the top-level
mapping in `registry/models.yaml` and `registry/tools.yaml`.
