from __future__ import annotations

from dataclasses import dataclass, field

from .loader import load_models, load_presets, load_tools
from .models import ModelSpec, ProfilePreset, ToolSpec


@dataclass
class Registry:
    models: dict[str, ModelSpec] = field(default_factory=dict)
    tools: dict[str, ToolSpec] = field(default_factory=dict)
    presets: dict[str, ProfilePreset] = field(default_factory=dict)

    @classmethod
    def load(cls) -> Registry:
        return cls(
            models=load_models(),
            tools=load_tools(),
            presets=load_presets(),
        )
