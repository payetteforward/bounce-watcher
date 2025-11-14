#!/usr/bin/env python3
"""
Pro Tools Bounce Watcher
Monitors Pro Tools session folders for new mix files and automatically converts them to M4A.
"""

import os
import sys
import time
import subprocess
import logging
from pathlib import Path
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Configuration
# Monitors recursively - will find Audio Files folders at any depth within these root paths
WATCH_ROOTS = [
    "/Volumes/Great 8",
    # Add additional root folders to monitor:
    # "/Volumes/Another Drive",
    # "/Users/payetteforward/Music/ProTools Sessions",
]
AUDIO_FILES_FOLDER = "Audio Files"
MIX_FILE_PREFIX = "mix"  # case-insensitive match
ICLOUD_DOWNLOADS = Path("/Users/payetteforward/Library/Mobile Documents/com~apple~CloudDocs/Downloads")
STABILITY_CHECK_INTERVAL = 2  # seconds between stability checks
STABILITY_CHECKS_REQUIRED = 3  # number of consecutive checks with same size
CONVERTER_SCRIPT = Path(__file__).parent / "convert_mix.sh"

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(Path(__file__).parent / "bounce_watcher.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Track files being monitored for stability
files_being_watched = {}


class FileStabilityMonitor:
    """Monitors a file until it stops being written to"""

    def __init__(self, file_path, callback):
        self.file_path = Path(file_path)
        self.callback = callback
        self.size_history = []
        self.check_count = 0

    def check_stability(self):
        """Returns True if file is stable, False if still being written"""
        try:
            if not self.file_path.exists():
                logger.warning(f"File disappeared: {self.file_path}")
                return False

            current_size = self.file_path.stat().st_size

            if len(self.size_history) == 0:
                self.size_history.append(current_size)
                return False

            if current_size == self.size_history[-1]:
                self.check_count += 1
                if self.check_count >= STABILITY_CHECKS_REQUIRED:
                    logger.info(f"File stable: {self.file_path} ({current_size} bytes)")
                    return True
            else:
                # Size changed, reset counter
                self.check_count = 0
                self.size_history.append(current_size)
                logger.debug(f"File still growing: {self.file_path} ({current_size} bytes)")

            return False
        except Exception as e:
            logger.error(f"Error checking stability for {self.file_path}: {e}")
            return False


class MixFileHandler(FileSystemEventHandler):
    """Handles file system events for mix files in Audio Files folders"""

    def on_created(self, event):
        if event.is_directory:
            return

        file_path = Path(event.src_path)

        # Check if this is in an "Audio Files" folder
        if AUDIO_FILES_FOLDER not in file_path.parts:
            return

        # Check if filename starts with "mix" (case-insensitive)
        if not file_path.name.lower().startswith(MIX_FILE_PREFIX.lower()):
            return

        logger.info(f"New mix file detected: {file_path}")

        # Start monitoring this file for stability
        if str(file_path) not in files_being_watched:
            monitor = FileStabilityMonitor(file_path, self.process_stable_file)
            files_being_watched[str(file_path)] = monitor
            logger.info(f"Monitoring file for stability: {file_path}")

    def process_stable_file(self, file_path):
        """Called when a file has stabilized and is ready for processing"""
        logger.info(f"Processing stable file: {file_path}")

        try:
            # Get the parent directory name (the session name)
            # Path structure: .../SessionName/Audio Files/mix_file.wav
            audio_files_path = file_path.parent
            session_path = audio_files_path.parent
            session_name = session_path.name

            logger.info(f"Session: {session_name}")

            # Create subdirectory in iCloud Downloads if needed
            output_dir = ICLOUD_DOWNLOADS / session_name
            output_dir.mkdir(parents=True, exist_ok=True)

            # Call conversion script
            if not CONVERTER_SCRIPT.exists():
                logger.error(f"Converter script not found: {CONVERTER_SCRIPT}")
                return

            logger.info(f"Converting {file_path.name} to M4A...")
            result = subprocess.run(
                [str(CONVERTER_SCRIPT), str(file_path), str(output_dir)],
                capture_output=True,
                text=True,
                timeout=600  # 10 minute timeout
            )

            if result.returncode == 0:
                logger.info(f"Successfully converted: {file_path.name}")
                logger.info(f"Output directory: {output_dir}")
            else:
                logger.error(f"Conversion failed for {file_path.name}")
                logger.error(f"STDOUT: {result.stdout}")
                logger.error(f"STDERR: {result.stderr}")

        except subprocess.TimeoutExpired:
            logger.error(f"Conversion timeout for {file_path}")
        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}", exc_info=True)


def stability_check_loop():
    """Periodically checks all monitored files for stability"""
    while True:
        time.sleep(STABILITY_CHECK_INTERVAL)

        # Check each file being monitored
        files_to_remove = []
        for file_path_str, monitor in list(files_being_watched.items()):
            if monitor.check_stability():
                # File is stable, process it
                monitor.callback(monitor.file_path)
                files_to_remove.append(file_path_str)

        # Remove processed files from watch list
        for file_path_str in files_to_remove:
            del files_being_watched[file_path_str]


def find_audio_files_folders(root_path):
    """Recursively find all 'Audio Files' folders under the root path"""
    root = Path(root_path)
    audio_folders = []

    if not root.exists():
        logger.warning(f"Root path does not exist: {root_path}")
        return audio_folders

    logger.info(f"Scanning for Audio Files folders in: {root_path}")

    try:
        for path in root.rglob(AUDIO_FILES_FOLDER):
            if path.is_dir():
                audio_folders.append(path)
                logger.info(f"Found Audio Files folder: {path}")
    except PermissionError as e:
        logger.error(f"Permission denied scanning {root_path}: {e}")
    except Exception as e:
        logger.error(f"Error scanning {root_path}: {e}")

    return audio_folders


def main():
    """Main entry point"""
    logger.info("=" * 80)
    logger.info("Pro Tools Bounce Watcher Starting")
    logger.info("=" * 80)
    logger.info(f"Watch roots: {WATCH_ROOTS}")
    logger.info(f"Looking for files starting with: {MIX_FILE_PREFIX}")
    logger.info(f"Output directory: {ICLOUD_DOWNLOADS}")
    logger.info(f"Converter script: {CONVERTER_SCRIPT}")

    # Verify converter script exists
    if not CONVERTER_SCRIPT.exists():
        logger.error(f"Converter script not found at: {CONVERTER_SCRIPT}")
        logger.error("Please ensure convert_mix.sh is in the same directory as this script")
        sys.exit(1)

    # Set up file system observer
    event_handler = MixFileHandler()
    observer = Observer()

    # Watch each root directory
    watched_paths = []
    for root_path in WATCH_ROOTS:
        root = Path(root_path)
        if root.exists():
            observer.schedule(event_handler, str(root), recursive=True)
            watched_paths.append(root)
            logger.info(f"Watching: {root}")

            # Also log existing Audio Files folders
            audio_folders = find_audio_files_folders(root)
            if audio_folders:
                logger.info(f"Found {len(audio_folders)} existing Audio Files folders")
        else:
            logger.warning(f"Watch root does not exist: {root_path}")

    if not watched_paths:
        logger.error("No valid watch paths found. Exiting.")
        sys.exit(1)

    # Start observer
    observer.start()
    logger.info("File system observer started")

    # Start stability check loop in background
    import threading
    stability_thread = threading.Thread(target=stability_check_loop, daemon=True)
    stability_thread.start()
    logger.info("Stability monitor started")

    logger.info("Bounce watcher is running. Press Ctrl+C to stop.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Stopping bounce watcher...")
        observer.stop()

    observer.join()
    logger.info("Bounce watcher stopped")


if __name__ == "__main__":
    main()
