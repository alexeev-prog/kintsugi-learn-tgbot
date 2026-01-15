from pathlib import Path
from typing import List, Optional, Any
from pydantic import BaseModel, Field, validator
import tomli
import json


class DatabaseConfiguration(BaseModel):
    database_path: str = Field(default="bot_database.sqlite")

    @validator("database_path")
    def validate_database_path(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Database path cannot be empty")
        return value.strip()

    @property
    def connection_string(self) -> str:
        return f"sqlite:///{self.database_path}"


class Configuration(BaseModel):
    TOKEN: str = Field(..., min_length=10)
    ADMINS_IDS: List[int] = Field(..., min_items=1)
    TG_BOT_USERNAME: str = Field(..., min_length=3)
    database: DatabaseConfiguration
    debug: bool = Field(default=False)
    log_level: str = Field(
        default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$"
    )

    @validator("TG_BOT_USERNAME")
    def validate_bot_username(cls, value: str) -> str:
        if not value.startswith("@"):
            raise ValueError("Bot username must start with @")

        return value

    @validator("ADMINS_IDS")
    def validate_admin_ids(cls, value: List[int]) -> List[int]:
        if any(admin_id <= 0 for admin_id in value):
            raise ValueError("Admin IDs must be positive integers")
        return sorted(set(value))

    @classmethod
    def from_json_string(cls, json_string: str) -> "Configuration":
        data = json.loads(json_string)
        return cls(**data)

    @classmethod
    def from_json_file(cls, filepath: Path) -> "Configuration":
        with open(filepath, "r", encoding="utf-8") as file:
            data = json.load(file)
        return cls(**data)

    @classmethod
    def from_toml_dict(cls, toml_data: dict) -> "Configuration":
        return cls(**toml_data)


class ConfigFileLoader:
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self._validate_file_path()

    def _validate_file_path(self) -> None:
        if not self.file_path.exists():
            raise FileNotFoundError(f"Config file {self.file_path} not found")
        if not self.file_path.is_file():
            raise ValueError(f"{self.file_path} is not a file")

    def load(self) -> dict:
        raise NotImplementedError


class TomlConfigLoader(ConfigFileLoader):
    def load(self) -> dict:
        with open(self.file_path, "rb") as file:
            return tomli.load(file)


class JsonConfigLoader(ConfigFileLoader):
    def load(self) -> dict:
        with open(self.file_path, "r", encoding="utf-8") as file:
            return json.load(file)


class ConfigLoaderFactory:
    _loaders = {
        ".toml": TomlConfigLoader,
        ".json": JsonConfigLoader,
    }

    @classmethod
    def create_loader(cls, config_path: Path) -> ConfigFileLoader:
        suffix = config_path.suffix.lower()
        loader_class = cls._loaders.get(suffix)

        if not loader_class:
            supported = ", ".join(cls._loaders.keys())
            raise ValueError(f"Unsupported config format. Supported: {supported}")

        return loader_class(config_path)


class ConfigurationManager:
    def __init__(self, config_path: Optional[Path] = "botconfig.toml"):
        self.config_path = config_path
        self._loader = ConfigLoaderFactory.create_loader(self.config_path)
        self._config: Configuration = self._load_configuration()

    @property
    def config(self) -> Configuration:
        if self._config is None:
            self._config = self._load_configuration()
        return self._config

    def _load_configuration(self) -> Configuration:
        raw_data = self._loader.load()
        return Configuration.from_toml_dict(raw_data)

    def reload(self) -> None:
        self._config = self._load_configuration()

    def __getattr__(self, name: str) -> Any:
        return getattr(self.config, name)
