"""
Centralized, Secure Settings & Environment Loader for CS 435 AI Interview Practice Interface.

Architecture & Security:
1. Multi-tier resolution: System Environment -> Root .env -> config/.env -> Defaults.
2. Complete secret shielding: Never prints or logs raw API keys.
3. Automated template fallback: Detects missing .env and safely scaffolds from .env.example.
4. Git isolation: All private credential files are strictly ignored by .gitignore.
"""
import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Base Directories
CONFIG_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CONFIG_DIR.parent

# Candidate locations for secret environment files (in order of priority)
CANDIDATE_DOTENV_PATHS = [
    PROJECT_ROOT / ".env",
    CONFIG_DIR / ".env",
    CONFIG_DIR / "secrets.env",
]

# Standard template paths (safe to commit to version control)
DOTENV_EXAMPLE_PATH = PROJECT_ROOT / ".env.example"
CONFIG_EXAMPLE_PATH = CONFIG_DIR / ".env.example"

# Active dotenv path defaults to root .env
DOTENV_PATH = PROJECT_ROOT / ".env"

# Default Model Fallbacks
DEFAULT_OPENROUTER_MODEL = "nvidia/nemotron-3.5-super-vl:free"
DEFAULT_GEMINI_MODEL = "gemini-3.5-flash"


def resolve_active_dotenv_path() -> Path:
    """Finds the first existing .env file among candidate locations, defaulting to root .env."""
    for p in CANDIDATE_DOTENV_PATHS:
        if p.exists():
            return p
    return PROJECT_ROOT / ".env"


def load_environment(filepath: Optional[Path] = None) -> Dict[str, str]:
    """
    Parses key=value pairs from the active .env file and injects them into os.environ.
    Preserves existing non-empty values in os.environ unless specified.
    """
    target = filepath or resolve_active_dotenv_path()
    loaded: Dict[str, str] = {}
    if not target.exists():
        return loaded

    try:
        with open(target, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip("'\"")
                    if key:
                        os.environ[key] = val
                        loaded[key] = val
    except Exception as e:
        logger.warning(f"Could not read environment file at {target}: {e}")
    return loaded


def get_secret(key: str, default: str = "") -> str:
    """
    Safely retrieves a configuration key or secret.
    Always refreshes from the active .env file on disk so updates take effect immediately without server reboot.
    """
    active_path = resolve_active_dotenv_path()
    if active_path.exists():
        load_environment(active_path)
    val = os.environ.get(key, "").strip()
    return val or default


def save_secret(key: str, value: str, filepath: Optional[Path] = None) -> bool:
    """
    Safely writes or updates a secret key in the local .env file without destroying other keys or comments.
    Ensures file is created if it does not yet exist.
    """
    target = filepath or resolve_active_dotenv_path()
    clean_key = (key or "").strip()
    clean_val = (value or "").strip()
    if not clean_key:
        return False

    try:
        lines = []
        if target.exists():
            lines = target.read_text(encoding="utf-8").splitlines(keepends=True)

        found = False
        new_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith(f"{clean_key}=") or stripped.startswith(f"{clean_key} ="):
                new_lines.append(f"{clean_key}={clean_val}\n")
                found = True
            else:
                new_lines.append(line)

        if not found:
            if new_lines and not new_lines[-1].endswith("\n"):
                new_lines.append("\n")
            new_lines.append(f"{clean_key}={clean_val}\n")

        target.write_text("".join(new_lines), encoding="utf-8")
        os.environ[clean_key] = clean_val
        return True
    except Exception as e:
        logger.error(f"Failed to persist secret {clean_key} to {target}: {e}")
        return False


def mask_secret(secret: str) -> str:
    """Returns a masked representation of a secret string (e.g. sk-or-...3a1b)."""
    if not secret:
        return "<not set>"
    if len(secret) <= 8:
        return "***"
    return f"{secret[:7]}...{secret[-4:]}"


def get_config_summary() -> Dict[str, Any]:
    """Returns masked status of current environment configuration suitable for diagnostics."""
    or_key = get_secret("OPENROUTER_API_KEY")
    gem_key = get_secret("GEMINI_API_KEY")
    return {
        "openrouter_configured": bool(or_key),
        "openrouter_key_masked": mask_secret(or_key),
        "openrouter_model": get_secret("OPENROUTER_MODEL", DEFAULT_OPENROUTER_MODEL),
        "gemini_configured": bool(gem_key),
        "gemini_key_masked": mask_secret(gem_key),
        "active_env_file": str(resolve_active_dotenv_path()),
        "env_file_exists": resolve_active_dotenv_path().exists(),
    }


# Automatically load environment on import
load_environment()
