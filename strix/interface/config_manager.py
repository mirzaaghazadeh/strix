"""Configuration manager for Strix settings."""

import os
from pathlib import Path
from typing import Any

from dotenv import dotenv_values, set_key


class ConfigManager:
    """Manages Strix configuration stored in ~/.strix/.env"""
    
    CONFIG_DIR = Path.home() / ".strix"
    CONFIG_FILE = CONFIG_DIR / ".env"
    
    REQUIRED_KEYS = ["STRIX_LLM", "LLM_API_KEY"]
    OPTIONAL_KEYS = ["PERPLEXITY_API_KEY", "LLM_API_BASE", "OPENAI_API_BASE", "LITELLM_BASE_URL", "OLLAMA_API_BASE"]
    
    @classmethod
    def ensure_config_dir(cls) -> None:
        """Ensure the config directory exists."""
        cls.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if not cls.CONFIG_FILE.exists():
            cls.CONFIG_FILE.touch()
    
    @classmethod
    def load_config(cls) -> dict[str, str]:
        """Load configuration from ~/.strix/.env file."""
        cls.ensure_config_dir()
        
        if not cls.CONFIG_FILE.exists():
            return {}
        
        config = dotenv_values(cls.CONFIG_FILE)
        # Filter out None values
        return {k: v for k, v in config.items() if v is not None}
    
    @classmethod
    def save_config(cls, config: dict[str, str]) -> None:
        """Save configuration to ~/.strix/.env file."""
        cls.ensure_config_dir()
        
        for key, value in config.items():
            set_key(cls.CONFIG_FILE, key, value)
    
    @classmethod
    def get_value(cls, key: str, default: str = "") -> str:
        """Get a configuration value."""
        config = cls.load_config()
        return config.get(key, default)
    
    @classmethod
    def set_value(cls, key: str, value: str) -> None:
        """Set a configuration value."""
        config = cls.load_config()
        config[key] = value
        cls.save_config(config)
    
    @classmethod
    def get_all_config(cls) -> dict[str, str]:
        """Get all configuration values."""
        return cls.load_config()
    
    @classmethod
    def update_config(cls, updates: dict[str, str]) -> None:
        """Update multiple configuration values."""
        config = cls.load_config()
        config.update(updates)
        cls.save_config(config)
    
    @classmethod
    def apply_to_environment(cls) -> None:
        """Apply configuration to current environment."""
        config = cls.load_config()
        for key, value in config.items():
            if value:  # Only set non-empty values
                os.environ[key] = value

