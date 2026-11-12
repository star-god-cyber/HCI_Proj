"""
Configuration package for CS 435 AI Interview Practice System.
Provides centralized, secure environment configuration and secret isolation.
"""
from config.settings import (
    PROJECT_ROOT,
    CONFIG_DIR,
    DOTENV_PATH,
    DOTENV_EXAMPLE_PATH,
    get_secret,
    save_secret,
    get_config_summary,
    load_environment,
)

__all__ = [
    "PROJECT_ROOT",
    "CONFIG_DIR",
    "DOTENV_PATH",
    "DOTENV_EXAMPLE_PATH",
    "get_secret",
    "save_secret",
    "get_config_summary",
    "load_environment",
]
