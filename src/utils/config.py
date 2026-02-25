"""Configuration loader for AI Frontier Insight Bot."""

import os
import yaml

# Project root: two levels up from this file (src/utils/config.py → project root)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIG_DIR = os.path.join(PROJECT_ROOT, "config")
MEMORY_DIR = os.path.join(PROJECT_ROOT, "memory")
PROMPTS_DIR = os.path.join(PROJECT_ROOT, "prompts")
DRAFTS_DIR = os.path.join(CONFIG_DIR, "drafts")


def load_settings() -> dict:
    """Load settings.yaml and return as dict."""
    path = os.path.join(CONFIG_DIR, "settings.yaml")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_sources() -> dict:
    """Load sources.yaml and return as dict."""
    path = os.path.join(CONFIG_DIR, "sources.yaml")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_prompt(name: str, **kwargs) -> str:
    """Load a prompt template and format with kwargs.

    Args:
        name: Prompt file name without extension (e.g. "signal_extraction")
        **kwargs: Template variables to substitute

    Returns:
        Formatted prompt string
    """
    path = os.path.join(PROMPTS_DIR, f"{name}.txt")
    with open(path, "r", encoding="utf-8") as f:
        template = f.read()
    if kwargs:
        return template.format(**kwargs)
    return template


def get_timezone() -> str:
    """Return configured timezone string."""
    settings = load_settings()
    return settings.get("timezone", "Asia/Shanghai")
