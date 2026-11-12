"""
Zero-dependency .env loader for CS 435 AI Interview Practice System.
Acts as a backward-compatible interface delegating to centralized config.settings.
Ensures zero disruption across existing modules while keeping secrets strictly isolated.
"""
from pathlib import Path
from typing import Dict

from config.settings import (
    PROJECT_ROOT,
    DOTENV_PATH,
    load_environment,
    get_secret,
    save_secret,
)


def load_dotenv_file(filepath: Path = DOTENV_PATH) -> Dict[str, str]:
    """Parses key=value pairs from the .env file and injects them into os.environ."""
    return load_environment(filepath)


def get_env_variable(key: str, default: str = "") -> str:
    """Retrieves an environment variable, refreshing from the active .env if currently empty."""
    return get_secret(key, default)


# Auto-load on import
load_dotenv_file()
