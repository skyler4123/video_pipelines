from __future__ import annotations

import json
from pathlib import Path

from ..errors import AdapterError
from .base import AdapterResult, BaseAdapter, Job


class MockAdapter(BaseAdapter):
    """A deterministic, non-rendering adapter for testing the control plane."""

    name = "mock"

    def run(self, job: Job) -> AdapterResult:
        if job.profile == "final":
            raise AdapterError("the mock adapter cannot produce final output")
        if job.output_dir is None:
            raise AdapterError("mock stage has no output directory")
        job.output_dir.mkdir(parents=True, exist_ok=True)
        target = job.output_dir / "mock-output.txt"
        payload = {
            "simulated": True,
            "run_id": job.run_id,
            "project": job.project_id,
            "shot": job.shot_id,
            "stage": job.stage_id,
            "profile": job.profile,
            "model": job.model_id,
            "params": job.params,
            "inputs": [str(path) for path in job.input_paths],
        }
        target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return AdapterResult(
            outputs=[target],
            warnings=["mock adapter: no real media was generated"],
            extra={"simulated": True},
        )
