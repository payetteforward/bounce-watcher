"""
Utility functions for Bounce Watcher.

Handles logging, notifications, and other common utilities.
"""

import logging
import subprocess
from pathlib import Path
from typing import Optional


def setup_logging(log_file: Optional[str] = None, level: str = "INFO") -> logging.Logger:
    """
    Set up logging configuration.

    Args:
        log_file: Path to log file. If None, logs to console only.
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Returns:
        Configured logger instance
    """
    # Create logger
    logger = logging.getLogger("bounce_watcher")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove existing handlers
    logger.handlers.clear()

    # Create formatters
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (if log file specified)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def send_notification(title: str, message: str, subtitle: Optional[str] = None) -> None:
    """
    Send macOS notification using osascript.

    Args:
        title: Notification title
        message: Notification message
        subtitle: Optional subtitle
    """
    try:
        # Build AppleScript command
        script = f'display notification "{message}" with title "{title}"'
        if subtitle:
            script = f'display notification "{message}" with title "{title}" subtitle "{subtitle}"'

        subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            timeout=5
        )
    except Exception as e:
        # Don't fail if notification fails
        print(f"Warning: Failed to send notification: {e}")


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human-readable format.

    Args:
        size_bytes: Size in bytes

    Returns:
        Formatted size string (e.g., "1.5 MB", "3.2 GB")
    """
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"


def format_duration(seconds: float) -> str:
    """
    Format duration in human-readable format.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted duration string (e.g., "1m 30s", "45s")
    """
    if seconds < 60:
        return f"{seconds:.1f}s"

    minutes = int(seconds // 60)
    remaining_seconds = seconds % 60

    if minutes < 60:
        return f"{minutes}m {remaining_seconds:.0f}s"

    hours = int(minutes // 60)
    remaining_minutes = minutes % 60
    return f"{hours}h {remaining_minutes}m"


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename by removing invalid characters.

    Args:
        filename: Original filename

    Returns:
        Sanitized filename
    """
    # Replace invalid characters with underscores
    invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
    sanitized = filename
    for char in invalid_chars:
        sanitized = sanitized.replace(char, '_')
    return sanitized


def get_session_name(file_path: str) -> Optional[str]:
    """
    Extract Pro Tools session name from file path.

    Assumes structure: .../SessionName/Audio Files/mix_file.wav

    Args:
        file_path: Full path to audio file

    Returns:
        Session name or None if cannot be determined
    """
    path = Path(file_path)

    # Walk up the path to find "Audio Files" folder
    for parent in path.parents:
        if parent.name == "Audio Files":
            # Session name is the parent of "Audio Files"
            session_parent = parent.parent
            return session_parent.name

    return None


def is_mix_file(filename: str, prefix: str = "mix") -> bool:
    """
    Check if filename is a mix file.

    Args:
        filename: File name to check
        prefix: Prefix to match (case-insensitive)

    Returns:
        True if filename starts with prefix (case-insensitive)
    """
    return filename.lower().startswith(prefix.lower())


def get_file_extension(filename: str) -> str:
    """
    Get file extension (lowercase, without dot).

    Args:
        filename: File name

    Returns:
        Lowercase extension without dot (e.g., "wav", "aiff")
    """
    path = Path(filename)
    return path.suffix.lstrip('.').lower()


def is_audio_file(filename: str) -> bool:
    """
    Check if file is a supported audio file.

    Args:
        filename: File name to check

    Returns:
        True if file has supported audio extension
    """
    supported_extensions = ['wav', 'aiff', 'aif']
    ext = get_file_extension(filename)
    return ext in supported_extensions
