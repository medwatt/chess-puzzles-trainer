from __future__ import annotations

import uuid
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from chess_puzzles.json_config import load_json_object, save_json_object
from chess_puzzles.platform.paths import user_config_dir


DEFAULT_ENGINE_CONFIG_PATH = user_config_dir() / "engines.json"


@dataclass(frozen=True, slots=True)
class EngineDefinition:
    engine_id: str
    name: str
    command: str
    threads: int = 1
    time_limit_seconds: float = 1.0
    depth: int = 16
    options: dict[str, str | int | float | bool] = field(default_factory=dict)

    def with_validated_values(self) -> "EngineDefinition":
        return replace(
            self,
            engine_id=self.engine_id.strip() or uuid.uuid4().hex,
            name=self.name.strip(),
            command=self.command.strip(),
            threads=max(1, min(256, int(self.threads))),
            time_limit_seconds=max(0.1, min(300.0, float(self.time_limit_seconds))),
            depth=max(1, min(128, int(self.depth))),
        )

    def to_json(self) -> dict[str, Any]:
        return {
            "id": self.engine_id,
            "name": self.name,
            "command": self.command,
            "threads": self.threads,
            "time_limit_seconds": self.time_limit_seconds,
            "depth": self.depth,
            "options": self.options,
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "EngineDefinition":
        options = data.get("options", {})
        if not isinstance(options, dict):
            options = {}
        return cls(
            engine_id=_string_value(data, "id", uuid.uuid4().hex),
            name=_string_value(data, "name", "Engine"),
            command=_string_value(data, "command", ""),
            threads=_int_value(data, "threads", 1),
            time_limit_seconds=_float_value(data, "time_limit_seconds", 1.0),
            depth=_int_value(data, "depth", 16),
            options=options,
        ).with_validated_values()


@dataclass(frozen=True, slots=True)
class EngineConfig:
    engines: tuple[EngineDefinition, ...] = ()
    default_engine_id: str = ""

    @property
    def default_engine(self) -> EngineDefinition | None:
        for engine in self.engines:
            if engine.engine_id == self.default_engine_id:
                return engine
        return self.engines[0] if self.engines else None

    def to_json(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "default_engine_id": self.default_engine_id,
            "engines": [engine.to_json() for engine in self.engines],
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "EngineConfig":
        engines = tuple(
            EngineDefinition.from_json(item)
            for item in data.get("engines", [])
            if isinstance(item, dict) and _string_value(item, "command", "")
        )
        default_engine_id = _string_value(data, "default_engine_id", "")
        if default_engine_id not in {engine.engine_id for engine in engines}:
            default_engine_id = engines[0].engine_id if engines else ""
        return cls(engines=engines, default_engine_id=default_engine_id)


def load_engine_config(path: str | Path = DEFAULT_ENGINE_CONFIG_PATH) -> EngineConfig:
    config_path = Path(path)
    if not config_path.exists():
        return EngineConfig()
    return EngineConfig.from_json(load_json_object(config_path, error_message="engines.json must contain a JSON object"))


def save_engine_config(config: EngineConfig, path: str | Path = DEFAULT_ENGINE_CONFIG_PATH) -> None:
    save_json_object(path, config.to_json())


def new_engine_definition(
    name: str,
    command: str,
    threads: int = 1,
    time_limit_seconds: float = 1.0,
    depth: int = 16,
) -> EngineDefinition:
    return EngineDefinition(
        engine_id=uuid.uuid4().hex,
        name=name,
        command=command,
        threads=threads,
        time_limit_seconds=time_limit_seconds,
        depth=depth,
    ).with_validated_values()


def _string_value(data: dict[str, Any], key: str, default: str) -> str:
    value = data.get(key, default)
    return value.strip() if isinstance(value, str) else default


def _int_value(data: dict[str, Any], key: str, default: int) -> int:
    value = data.get(key, default)
    return value if isinstance(value, int) and not isinstance(value, bool) else default


def _float_value(data: dict[str, Any], key: str, default: float) -> float:
    value = data.get(key, default)
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else default
