from typing import List, Union, Dict, Any, Protocol, Optional
from abc import ABC, abstractmethod
import logging
import sys
from pathlib import Path
from loguru import logger
import json


class LogFormatter(Protocol):
    def format(self, record: Dict[str, Any]) -> str: ...


class ConsoleFormatter:
    def format(self, record: Dict[str, Any]) -> str:
        level_color = self._get_level_color(record["level"].name)
        return f"<green>{record['time']:YYYY-MM-DD HH:mm:ss.SSS}</green> | {level_color} | <cyan>{record['name']}</cyan>:<cyan>{record['function']}</cyan>:<cyan>{record['line']}</cyan> - <level>{record['message']}</level>\n"

    def _get_level_color(self, level: str) -> str:
        colors = {
            "DEBUG": "<blue>{level: <8}</blue>",
            "INFO": "<green>{level: <8}</green>",
            "WARNING": "<yellow>{level: <8}</yellow>",
            "ERROR": "<red>{level: <8}</red>",
            "CRITICAL": "<bold><red>{level: <8}</red></bold>",
        }
        return colors.get(level, "<level>{level: <8}</level>")


class FileFormatter:
    def format(self, record: Dict[str, Any]) -> str:
        return "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}"


class JsonFormatter:
    def format(self, record: Dict[str, Any]) -> str:
        return json.dumps(
            {
                "timestamp": str(record["time"]),
                "level": record["level"].name,
                "name": record["name"],
                "function": record["function"],
                "line": record["line"],
                "message": record["message"],
                "exception": str(record["exception"])
                if record.get("exception")
                else None,
            }
        )


class LogHandler(ABC):
    @abstractmethod
    def get_config(self) -> Dict[str, Any]: ...


class ConsoleHandler(LogHandler):
    def __init__(self, level: str, formatter: LogFormatter, colors: bool = True):
        self.level = level
        self.formatter = formatter
        self.colors = colors

    def get_config(self) -> Dict[str, Any]:
        return {
            "sink": sys.stderr,
            "level": self.level,
            "format": self.formatter.format,
            "colorize": self.colors,
            "backtrace": True,
            "diagnose": True,
        }


class FileHandler(LogHandler):
    def __init__(
        self,
        filepath: Path,
        level: str,
        formatter: LogFormatter,
        rotation: str = "10 MB",
        retention: str = "30 days",
    ):
        self.filepath = filepath
        self.level = level
        self.formatter = formatter
        self.rotation = rotation
        self.retention = retention

    def get_config(self) -> Dict[str, Any]:
        self._ensure_directory_exists()
        return {
            "sink": str(self.filepath),
            "level": self.level,
            "format": self.formatter.format,
            "rotation": self.rotation,
            "retention": self.retention,
            "compression": "gz",
            "backtrace": True,
            "diagnose": True,
            "encoding": "utf-8",
        }

    def _ensure_directory_exists(self) -> None:
        self.filepath.parent.mkdir(parents=True, exist_ok=True)


class LoggingInterceptionManager:
    def __init__(self, level: str):
        self.level = level
        self.handler = self._create_intercept_handler()

    def _create_intercept_handler(self) -> logging.Handler:
        class InterceptHandler(logging.Handler):
            def emit(self, record) -> None:
                try:
                    level = logger.level(record.levelname).name
                except ValueError:
                    level = record.levelno

                frame, depth = logging.currentframe(), 2
                while frame.f_code.co_filename == logging.__file__:
                    frame = frame.f_back
                    depth += 1

                logger.opt(depth=depth, exception=record.exc_info).log(
                    level, record.getMessage()
                )

        return InterceptHandler()

    def setup(self) -> None:
        logging.basicConfig(
            handlers=[self.handler], level=logging.getLevelName(self.level), force=True
        )


class LoggerConfigurator:
    def __init__(
        self,
        level: str = "DEBUG",
        log_file: Optional[str] = None,
        rotation: str = "10 MB",
        retention: str = "30 days",
        colors: bool = True,
        json_format: bool = False,
        ignored_loggers: Optional[List[str]] = None,
    ):
        self.level = level
        self.log_file = log_file
        self.rotation = rotation
        self.retention = retention
        self.colors = colors
        self.json_format = json_format
        self.ignored_loggers = ignored_loggers or []

    def configure(self) -> None:
        logger.remove()
        self._add_handlers()
        self._setup_logging_interception()
        self._disable_ignored_loggers()
        logger.info("Logging is successfully configured")

    def _add_handlers(self) -> None:
        self._add_console_handler()
        if self.log_file:
            self._add_file_handler()

    def _add_console_handler(self) -> None:
        formatter = JsonFormatter() if self.json_format else ConsoleFormatter()
        handler = ConsoleHandler(self.level, formatter, self.colors)
        logger.add(**handler.get_config())

    def _add_file_handler(self) -> None:
        filepath = Path(self.log_file)
        formatter = JsonFormatter() if self.json_format else FileFormatter()
        handler = FileHandler(
            filepath, self.level, formatter, self.rotation, self.retention
        )
        logger.add(**handler.get_config())

    def _setup_logging_interception(self) -> None:
        manager = LoggingInterceptionManager(self.level)
        manager.setup()

    def _disable_ignored_loggers(self) -> None:
        for logger_name in self.ignored_loggers:
            logger.disable(logger_name)


def setup_logger(
    level: Union[str, int] = "DEBUG",
    ignored: Optional[List[str]] = None,
    log_file: Optional[str] = None,
    rotation: str = "10 MB",
    retention: str = "30 days",
    colors: bool = True,
    json_format: bool = False,
) -> None:
    if isinstance(level, int):
        level = logging.getLevelName(level)

    configurator = LoggerConfigurator(
        level=level,
        log_file=log_file,
        rotation=rotation,
        retention=retention,
        colors=colors,
        json_format=json_format,
        ignored_loggers=ignored,
    )

    configurator.configure()
