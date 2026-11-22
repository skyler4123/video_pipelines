from __future__ import annotations

from ..errors import AdapterError
from .base import AdapterResult, BaseAdapter, Job


class DiffusersAdapter(BaseAdapter):
    name = "diffusers"

    def run(self, job: Job) -> AdapterResult:
        raise AdapterError(
            "the diffusers adapter is a stub. Add your local pipeline in "
            "runner/adapters/diffusers.py, or use ComfyUI for this stage."
        )


class HostedAPIAdapter(BaseAdapter):
    name = "hosted_api"

    def run(self, job: Job) -> AdapterResult:
        raise AdapterError(
            "the hosted_api adapter is a stub. Add the provider request and "
            "download logic in runner/adapters/hosted_api.py, and record the "
            "provider request id and cost in the manifest."
        )
