"""
Audio file conversion for Bounce Watcher.

Orchestrates the conversion of audio files using the convert_mix.sh script.
"""

import subprocess
import time
from pathlib import Path
from typing import Dict, Any, Optional
import logging

from .utils import format_file_size, format_duration


class ConversionError(Exception):
    """Raised when audio conversion fails."""
    pass


class AudioConverter:
    """
    Manages audio file conversion.

    Uses the convert_mix.sh script to convert WAV/AIFF files to M4A.
    """

    def __init__(self, config: Dict[str, Any], script_dir: Path):
        """
        Initialize audio converter.

        Args:
            config: Configuration dictionary with conversion settings
            script_dir: Directory containing convert_mix.sh script
        """
        self.config = config
        self.sample_rate = config.get("sample_rate", 48000)
        self.script_path = script_dir / "scripts" / "convert_mix.sh"
        self.logger = logging.getLogger("bounce_watcher.converter")

        # Verify script exists
        if not self.script_path.exists():
            raise ConversionError(f"Conversion script not found: {self.script_path}")
        if not self.script_path.is_file():
            raise ConversionError(f"Conversion script is not a file: {self.script_path}")

    def convert(self, input_file: str, output_file: str) -> None:
        """
        Convert audio file from WAV/AIFF to M4A.

        Args:
            input_file: Path to input audio file
            output_file: Path to output M4A file (the script will use the directory)

        Raises:
            ConversionError: If conversion fails
        """
        input_path = Path(input_file)
        output_path = Path(output_file)

        # Validate input file
        if not input_path.exists():
            raise ConversionError(f"Input file does not exist: {input_file}")
        if not input_path.is_file():
            raise ConversionError(f"Input path is not a file: {input_file}")

        # Get input file size for logging
        input_size = input_path.stat().st_size

        self.logger.info(f"Starting conversion: {input_path.name} ({format_file_size(input_size)})")
        self.logger.debug(f"Input: {input_file}")
        self.logger.debug(f"Output directory: {output_path.parent}")
        self.logger.debug(f"Sample rate: {self.sample_rate} Hz")

        # Ensure output directory exists
        output_dir = output_path.parent
        output_dir.mkdir(parents=True, exist_ok=True)

        # Run conversion script (pass directory, not full file path)
        start_time = time.time()
        try:
            result = subprocess.run(
                [
                    str(self.script_path),
                    str(input_path),
                    str(output_dir),  # Script expects directory, not file path
                    str(self.sample_rate)
                ],
                capture_output=True,
                text=True,
                check=True
            )

            duration = time.time() - start_time

            # Script may have created a unique filename, so find the actual output file
            # Look for files matching the base name in the output directory
            base_name = input_path.stem  # filename without extension
            output_files = list(output_dir.glob(f"{base_name}*.m4a"))

            # Find the most recently modified file matching the pattern
            if output_files:
                actual_output = max(output_files, key=lambda p: p.stat().st_mtime)
                output_size = actual_output.stat().st_size
                compression_ratio = (1 - output_size / input_size) * 100 if input_size > 0 else 0

                self.logger.info(
                    f"Conversion complete: {actual_output.name} "
                    f"({format_file_size(output_size)}, "
                    f"{compression_ratio:.1f}% smaller, "
                    f"took {format_duration(duration)})"
                )
            else:
                raise ConversionError(f"Output file was not created in {output_dir}")

            # Log conversion script output if in debug mode
            if result.stdout:
                self.logger.debug(f"Script output: {result.stdout}")

        except subprocess.CalledProcessError as e:
            duration = time.time() - start_time
            error_msg = e.stderr.strip() if e.stderr else str(e)
            self.logger.error(f"Conversion failed after {format_duration(duration)}: {error_msg}")
            raise ConversionError(f"Conversion failed: {error_msg}")
        except Exception as e:
            duration = time.time() - start_time
            self.logger.error(f"Conversion failed after {format_duration(duration)}: {e}")
            raise ConversionError(f"Conversion failed: {e}")

    def __repr__(self) -> str:
        """String representation of audio converter."""
        return f"AudioConverter(sample_rate={self.sample_rate})"


def get_audio_converter(config: Dict[str, Any], script_dir: Path) -> AudioConverter:
    """
    Create and return an audio converter from configuration.

    Args:
        config: Configuration dictionary
        script_dir: Directory containing conversion scripts

    Returns:
        Configured AudioConverter instance
    """
    conv_config = config.get("conversion", {})
    return AudioConverter(conv_config, script_dir)
