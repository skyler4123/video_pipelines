from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any

from ..errors import AdapterError
from .base import AdapterResult, BaseAdapter, Job


class ComfyUIAdapter(BaseAdapter):
    name = "comfyui"

    def __init__(self, endpoint: str | None = None) -> None:
        self.endpoint = (endpoint or os.environ.get("COMFYUI_URL") or "http://127.0.0.1:8188").rstrip("/")
        self.timeout = float(os.environ.get("COMFYUI_TIMEOUT", "1800"))
        self.poll_interval = float(os.environ.get("COMFYUI_POLL_INTERVAL", "2"))

    def _url(self, path: str) -> str:
        return f"{self.endpoint}{path}"

    def _json_request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        timeout: float = 30,
    ) -> Any:
        data = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            self._url(path), data=data, headers=headers, method=method
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise AdapterError(
                f"ComfyUI returned HTTP {exc.code} for {path}: {body[:2000]}"
            ) from exc
        except urllib.error.URLError as exc:
            raise AdapterError(
                f"cannot reach ComfyUI at {self.endpoint}: {exc.reason}. "
                "Start ComfyUI or set COMFYUI_URL."
            ) from exc
        try:
            return json.loads(body) if body else {}
        except json.JSONDecodeError as exc:
            raise AdapterError(
                f"ComfyUI returned invalid JSON for {path}: {body[:500]}"
            ) from exc

    def health(self) -> dict[str, Any]:
        return self._json_request("GET", "/system_stats", timeout=5)

    def run(self, job: Job) -> AdapterResult:
        if job.workflow is None:
            raise AdapterError("ComfyUI stage has no workflow")
        if job.output_dir is None:
            raise AdapterError("ComfyUI stage has no output directory")
        self.health()

        client_id = str(uuid.uuid4())
        response = self._json_request(
            "POST",
            "/prompt",
            {"prompt": job.workflow, "client_id": client_id},
        )
        prompt_id = response.get("prompt_id")
        if not prompt_id:
            raise AdapterError(f"ComfyUI did not return a prompt_id: {response}")
        node_errors = response.get("node_errors") or {}
        if node_errors:
            raise AdapterError(
                "ComfyUI rejected the workflow: "
                + json.dumps(node_errors, indent=2)[:4000]
            )

        history = self._wait_for(prompt_id)
        outputs = self._download_outputs(prompt_id, history, job.output_dir)
        warnings: list[str] = []
        if not outputs:
            warnings.append(
                "ComfyUI completed but returned no downloadable output files"
            )
        return AdapterResult(
            outputs=outputs,
            warnings=warnings,
            extra={"prompt_id": prompt_id, "client_id": client_id},
        )

    def _wait_for(self, prompt_id: str) -> dict[str, Any]:
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            history = self._json_request("GET", f"/history/{prompt_id}", timeout=30)
            entry = history.get(prompt_id) if isinstance(history, dict) else None
            if isinstance(entry, dict):
                status = entry.get("status") or {}
                status_str = status.get("status_str") if isinstance(status, dict) else None
                if status_str == "error":
                    messages = status.get("messages") if isinstance(status, dict) else None
                    raise AdapterError(
                        "ComfyUI execution failed: "
                        + json.dumps(messages or status, indent=2)[:4000]
                    )
                if status.get("completed") or status_str == "success":
                    return entry
            time.sleep(self.poll_interval)
        raise AdapterError(
            f"ComfyUI did not finish prompt {prompt_id} within {self.timeout:.0f}s"
        )

    def _download_outputs(
        self,
        prompt_id: str,
        history: dict[str, Any],
        output_dir: Path,
    ) -> list[Path]:
        output_dir.mkdir(parents=True, exist_ok=True)
        files: list[Path] = []
        for node_id, node_output in (history.get("outputs") or {}).items():
            for item in self._find_files(node_output):
                filename = item.get("filename")
                if not filename:
                    continue
                subfolder = item.get("subfolder") or ""
                kind = item.get("type") or "output"
                query = urllib.parse.urlencode(
                    {"filename": filename, "subfolder": subfolder, "type": kind}
                )
                data = self._download(f"/view?{query}")
                target = output_dir / Path(filename).name
                if target.exists():
                    target = output_dir / f"{node_id}_{target.name}"
                target.write_bytes(data)
                files.append(target)
        return files

    def _find_files(self, value: Any) -> list[dict[str, Any]]:
        found: list[dict[str, Any]] = []
        if isinstance(value, dict):
            if isinstance(value.get("filename"), str):
                found.append(value)
            else:
                for child in value.values():
                    found.extend(self._find_files(child))
        elif isinstance(value, list):
            for child in value:
                found.extend(self._find_files(child))
        return found

    def _download(self, path: str) -> bytes:
        try:
            with urllib.request.urlopen(self._url(path), timeout=120) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise AdapterError(
                f"ComfyUI download failed with HTTP {exc.code}: {body[:1000]}"
            ) from exc
        except urllib.error.URLError as exc:
            raise AdapterError(
                f"ComfyUI download failed: {exc.reason}"
            ) from exc
