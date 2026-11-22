from __future__ import annotations

from ..errors import AdapterError
from .base import AdapterResult, BaseAdapter, Job
from .comfyui import ComfyUIAdapter
from .ffmpeg import FFmpegAdapter
from .mock import MockAdapter
from .stubs import DiffusersAdapter, HostedAPIAdapter


def get_adapter(name: str) -> BaseAdapter:
    if name == "comfyui":
        return ComfyUIAdapter()
    if name == "ffmpeg":
        return FFmpegAdapter()
    if name == "mock":
        return MockAdapter()
    if name == "diffusers":
        return DiffusersAdapter()
    if name == "hosted_api":
        return HostedAPIAdapter()
    raise AdapterError(f"unknown adapter {name!r}")
