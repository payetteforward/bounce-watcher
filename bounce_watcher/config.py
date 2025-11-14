"""
Configuration management for Bounce Watcher.

Handles loading, saving, validation, and migration of TOML configuration files.
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any

# Handle tomli import for different Python versions
if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomli as tomllib
    except ImportError:
        raise ImportError("tomli is required for Python < 3.11. Install with: pip install tomli")

try:
    import tomli_w
except ImportError:
    raise ImportError("tomli-w is required. Install with: pip install tomli-w")


class ConfigError(Exception):
    """Raised when configuration is invalid."""
    pass


class Config:
    """
    Configuration manager for Bounce Watcher.

    Handles loading, saving, and validating TOML configuration files.
    """

    # Default configuration file location
    DEFAULT_CONFIG_DIR = Path.home() / ".config" / "bounce-watcher"
    DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "config.toml"

    # Default configuration values
    # These are sensible defaults - users should customize via config file or wizard
    DEFAULTS = {
        "source": {
            "mode": "specific_folders",  # or "all_external_drives"
            "folders": [],  # User must configure via wizard
            "audio_files_folder": "Audio Files",
            "mix_file_prefix": "mix",
        },
        "destination": {
            "mode": "icloud",  # or "nas" or "custom"
            "icloud_path": str(Path.home() / "Library" / "Mobile Documents" / "com~apple~CloudDocs" / "Downloads"),
            "nas_url": "smb://your-nas-server.local/share",
            "nas_username": "your-username",
            "nas_mount_point": "/Volumes/NAS",
            "custom_path": str(Path.home() / "Music" / "Bounce Watcher"),
        },
        "conversion": {
            "sample_rate": 48000,
            "stability_check_interval": 2,
            "stability_checks_required": 3,
        },
        "logging": {
            "log_file": str(Path.home() / ".local" / "share" / "bounce-watcher" / "bounce_watcher.log"),
            "level": "INFO",
        },
    }

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize configuration manager.

        Args:
            config_path: Path to configuration file. If None, uses default location.
        """
        self.config_path = config_path or self.DEFAULT_CONFIG_FILE
        self.config: Dict[str, Any] = {}

    def load(self) -> Dict[str, Any]:
        """
        Load configuration from file.

        If file doesn't exist, returns default configuration.

        Returns:
            Configuration dictionary

        Raises:
            ConfigError: If configuration file is invalid
        """
        if not self.config_path.exists():
            self.config = self._get_defaults()
            return self.config

        try:
            with open(self.config_path, "rb") as f:
                self.config = tomllib.load(f)
            self._validate()
            return self.config
        except Exception as e:
            raise ConfigError(f"Failed to load configuration from {self.config_path}: {e}")

    def save(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Save configuration to file.

        Args:
            config: Configuration dictionary to save. If None, saves current config.

        Raises:
            ConfigError: If configuration is invalid or cannot be saved
        """
        if config is not None:
            self.config = config

        self._validate()

        # Ensure config directory exists
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(self.config_path, "wb") as f:
                tomli_w.dump(self.config, f)
        except Exception as e:
            raise ConfigError(f"Failed to save configuration to {self.config_path}: {e}")

    def _get_defaults(self) -> Dict[str, Any]:
        """
        Get default configuration.

        Returns:
            Default configuration dictionary
        """
        import copy
        return copy.deepcopy(self.DEFAULTS)

    def _validate(self) -> None:
        """
        Validate current configuration.

        Raises:
            ConfigError: If configuration is invalid
        """
        # Check required sections
        required_sections = ["source", "destination", "conversion", "logging"]
        for section in required_sections:
            if section not in self.config:
                raise ConfigError(f"Missing required section: [{section}]")

        # Validate source section
        source = self.config["source"]
        if "mode" not in source:
            raise ConfigError("Missing 'mode' in [source] section")
        if source["mode"] not in ["specific_folders", "all_external_drives"]:
            raise ConfigError(f"Invalid source mode: {source['mode']}")
        if source["mode"] == "specific_folders" and not source.get("folders"):
            raise ConfigError("'folders' must be specified when source mode is 'specific_folders'")

        # Validate destination section
        dest = self.config["destination"]
        if "mode" not in dest:
            raise ConfigError("Missing 'mode' in [destination] section")
        if dest["mode"] not in ["icloud", "nas", "custom"]:
            raise ConfigError(f"Invalid destination mode: {dest['mode']}")
        if dest["mode"] == "icloud" and not dest.get("icloud_path"):
            raise ConfigError("'icloud_path' must be specified when destination mode is 'icloud'")
        if dest["mode"] == "nas":
            required_nas_keys = ["nas_url", "nas_username", "nas_mount_point"]
            for key in required_nas_keys:
                if not dest.get(key):
                    raise ConfigError(f"'{key}' must be specified when destination mode is 'nas'")
        if dest["mode"] == "custom" and not dest.get("custom_path"):
            raise ConfigError("'custom_path' must be specified when destination mode is 'custom'")

        # Validate conversion section
        conv = self.config["conversion"]
        if "sample_rate" not in conv:
            raise ConfigError("Missing 'sample_rate' in [conversion] section")
        if not isinstance(conv["sample_rate"], int) or conv["sample_rate"] <= 0:
            raise ConfigError("'sample_rate' must be a positive integer")

    def get(self, section: str, key: str, default: Any = None) -> Any:
        """
        Get configuration value.

        Args:
            section: Configuration section
            key: Configuration key
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        return self.config.get(section, {}).get(key, default)

    def set(self, section: str, key: str, value: Any) -> None:
        """
        Set configuration value.

        Args:
            section: Configuration section
            key: Configuration key
            value: Value to set
        """
        if section not in self.config:
            self.config[section] = {}
        self.config[section][key] = value

    def exists(self) -> bool:
        """
        Check if configuration file exists.

        Returns:
            True if configuration file exists, False otherwise
        """
        return self.config_path.exists()

    def create_default(self) -> None:
        """
        Create default configuration file.

        Raises:
            ConfigError: If configuration file already exists or cannot be created
        """
        if self.exists():
            raise ConfigError(f"Configuration file already exists: {self.config_path}")

        self.config = self._get_defaults()
        self.save()

    def migrate_from_legacy(self, legacy_config: Dict[str, Any]) -> None:
        """
        Migrate from legacy hard-coded configuration.

        Args:
            legacy_config: Legacy configuration dictionary
        """
        # Start with defaults
        self.config = self._get_defaults()

        # Apply legacy values
        if "watch_roots" in legacy_config:
            self.config["source"]["folders"] = legacy_config["watch_roots"]
        if "icloud_downloads" in legacy_config:
            self.config["destination"]["icloud_path"] = legacy_config["icloud_downloads"]
        if "audio_files_folder" in legacy_config:
            self.config["source"]["audio_files_folder"] = legacy_config["audio_files_folder"]
        if "mix_file_prefix" in legacy_config:
            self.config["source"]["mix_file_prefix"] = legacy_config["mix_file_prefix"]

        self.save()

    def __repr__(self) -> str:
        """String representation of configuration."""
        return f"Config(path={self.config_path}, exists={self.exists()})"


def load_config(config_path: Optional[Path] = None) -> Config:
    """
    Load configuration from file.

    Args:
        config_path: Path to configuration file. If None, uses default location.

    Returns:
        Config object with loaded configuration

    Raises:
        ConfigError: If configuration is invalid
    """
    config = Config(config_path)
    config.load()
    return config
