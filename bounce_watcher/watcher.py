"""
File system watching for Bounce Watcher.

Monitors Pro Tools session folders for new mix files and triggers conversion.
"""

import time
import threading
import logging
from pathlib import Path
from typing import Dict, Callable
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from .utils import (
    get_session_name,
    is_mix_file,
    is_audio_file,
    send_notification
)


class FileStabilityMonitor:
    """
    Monitors a file until it stops being written to.

    Checks file size at regular intervals to ensure the file has finished
    being written before processing.
    """

    def __init__(
        self,
        file_path: str,
        callback: Callable,
        check_interval: int = 2,
        checks_required: int = 3
    ):
        """
        Initialize file stability monitor.

        Args:
            file_path: Path to file to monitor
            callback: Function to call when file is stable
            check_interval: Seconds between stability checks
            checks_required: Number of consecutive checks with same size required
        """
        self.file_path = Path(file_path)
        self.callback = callback
        self.check_interval = check_interval
        self.checks_required = checks_required
        self.size_history = []
        self.check_count = 0
        self.logger = logging.getLogger("bounce_watcher.stability")

    def check_stability(self) -> bool:
        """
        Check if file is stable (not being written to).

        Returns:
            True if file is stable, False if still being written
        """
        try:
            if not self.file_path.exists():
                self.logger.warning(f"File disappeared: {self.file_path}")
                return False

            current_size = self.file_path.stat().st_size

            # First check
            if len(self.size_history) == 0:
                self.size_history.append(current_size)
                return False

            # Compare with last check
            if current_size == self.size_history[-1]:
                self.check_count += 1
                if self.check_count >= self.checks_required:
                    self.logger.info(f"File stable: {self.file_path.name} ({current_size:,} bytes)")
                    return True
            else:
                # Size changed, reset counter
                self.check_count = 0
                self.size_history.append(current_size)
                self.logger.debug(f"File still growing: {self.file_path.name} ({current_size:,} bytes)")

            return False

        except Exception as e:
            self.logger.error(f"Error checking stability for {self.file_path}: {e}")
            return False


class MixFileHandler(FileSystemEventHandler):
    """
    Handles file system events for mix files in Audio Files folders.

    Detects new mix files and starts monitoring them for stability before processing.
    """

    def __init__(
        self,
        audio_folder_name: str,
        mix_prefix: str,
        on_stable_file: Callable,
        stability_interval: int = 2,
        stability_checks: int = 3,
        check_trigger=None
    ):
        """
        Initialize mix file handler.

        Args:
            audio_folder_name: Name of audio files folder to monitor
            mix_prefix: Prefix for mix files to detect
            on_stable_file: Callback function for stable files
            stability_interval: Seconds between stability checks
            stability_checks: Number of checks required for stability
            check_trigger: Optional threading.Event to signal when files need checking
        """
        super().__init__()
        self.audio_folder_name = audio_folder_name
        self.mix_prefix = mix_prefix
        self.on_stable_file = on_stable_file
        self.stability_interval = stability_interval
        self.stability_checks = stability_checks
        self.files_being_watched: Dict[str, FileStabilityMonitor] = {}
        self.check_trigger = check_trigger
        self.logger = logging.getLogger("bounce_watcher.handler")

    def on_created(self, event):
        """
        Handle file creation events.

        Args:
            event: File system event
        """
        if event.is_directory:
            return

        file_path = Path(event.src_path)

        # Check if this is in an audio files folder
        if self.audio_folder_name not in file_path.parts:
            return

        # Check if this is an audio file
        if not is_audio_file(file_path.name):
            return

        # Check if filename starts with mix prefix
        if not is_mix_file(file_path.name, self.mix_prefix):
            return

        self.logger.info(f"New mix file detected: {file_path.name}")

        # Start monitoring this file for stability
        file_path_str = str(file_path)
        if file_path_str not in self.files_being_watched:
            monitor = FileStabilityMonitor(
                file_path_str,
                self.on_stable_file,
                self.stability_interval,
                self.stability_checks
            )
            self.files_being_watched[file_path_str] = monitor
            self.logger.info(f"Monitoring file for stability: {file_path.name}")

            # Wake up the stability checker immediately
            if self.check_trigger:
                self.check_trigger.set()

    def check_all_files(self):
        """
        Check stability of all monitored files.

        Should be called periodically by the stability check loop.
        """
        files_to_remove = []

        for file_path_str, monitor in list(self.files_being_watched.items()):
            if monitor.check_stability():
                # File is stable, process it
                monitor.callback(monitor.file_path)
                files_to_remove.append(file_path_str)

        # Remove processed files from watch list
        for file_path_str in files_to_remove:
            del self.files_being_watched[file_path_str]


class BounceWatcher:
    """
    Main watcher class that orchestrates file monitoring and conversion.

    Supports dynamic drive monitoring for hot-plug detection.
    """

    def __init__(
        self,
        watch_roots: list,
        audio_folder_name: str,
        mix_prefix: str,
        destination_manager,
        audio_converter,
        source_manager=None,
        source_mode: str = "specific_folders",
        stability_interval: int = 2,
        stability_checks: int = 3
    ):
        """
        Initialize bounce watcher.

        Args:
            watch_roots: List of root directories to watch
            audio_folder_name: Name of audio files folder to monitor
            mix_prefix: Prefix for mix files to detect
            destination_manager: DestinationManager instance
            audio_converter: AudioConverter instance
            source_manager: Optional SourceManager for dynamic drive monitoring
            source_mode: Source mode ("specific_folders" or "all_external_drives")
            stability_interval: Seconds between stability checks
            stability_checks: Number of checks required for stability
        """
        self.watch_roots = watch_roots
        self.audio_folder_name = audio_folder_name
        self.mix_prefix = mix_prefix
        self.destination_manager = destination_manager
        self.audio_converter = audio_converter
        self.source_manager = source_manager
        self.source_mode = source_mode
        self.stability_interval = stability_interval
        self.stability_checks = stability_checks
        self.logger = logging.getLogger("bounce_watcher")

        # Track active watch handles for each drive (for dynamic removal)
        self.active_watches = {}  # {mount_point: watch_handle}

        # Create trigger event for efficient stability checking
        self.check_trigger = threading.Event()

        # Create event handler
        self.event_handler = MixFileHandler(
            audio_folder_name,
            mix_prefix,
            self.process_stable_file,
            stability_interval,
            stability_checks,
            check_trigger=self.check_trigger
        )

        # Create observer
        self.observer = Observer()
        self.stability_thread = None
        self.drive_monitor = None
        self.running = False

    def process_stable_file(self, file_path: Path):
        """
        Process a stable file (convert it).

        Args:
            file_path: Path to stable file to process
        """
        self.logger.info(f"Processing stable file: {file_path.name}")

        try:
            # Get session name from path
            session_name = get_session_name(str(file_path))
            if not session_name:
                self.logger.error(f"Could not determine session name for: {file_path}")
                send_notification(
                    "Bounce Watcher Error",
                    f"Could not determine session name for {file_path.name}"
                )
                return

            self.logger.info(f"Session: {session_name}")

            # Get destination path
            output_dir = self.destination_manager.get_destination_path(session_name)
            self.logger.info(f"Output directory: {output_dir}")

            # Generate output filename
            output_filename = file_path.stem + ".m4a"
            output_path = Path(output_dir) / output_filename

            # Convert file
            self.logger.info(f"Converting {file_path.name} to M4A...")
            send_notification(
                "Bounce Watcher",
                f"Converting {file_path.name}...",
                subtitle=session_name
            )

            self.audio_converter.convert(str(file_path), str(output_path))

            self.logger.info(f"Successfully converted: {file_path.name}")
            send_notification(
                "Bounce Watcher",
                f"Successfully converted {file_path.name}",
                subtitle=session_name
            )

        except Exception as e:
            self.logger.error(f"Error processing {file_path}: {e}", exc_info=True)
            send_notification(
                "Bounce Watcher Error",
                f"Failed to convert {file_path.name}: {str(e)}"
            )

    def _stability_check_loop(self):
        """
        Background thread that efficiently checks file stability.

        Uses event-driven waiting and adaptive polling to minimize CPU usage.
        Only actively checks when files are being monitored.
        """
        idle_interval = 30  # Check every 30 seconds when idle
        consecutive_idle_checks = 0
        max_idle_checks = 10  # After 10 idle checks (5 minutes), slow down further

        while self.running:
            # Check if there are files to monitor
            num_files = len(self.event_handler.files_being_watched)

            if num_files > 0:
                # Active mode: Check files at configured interval
                # Use Event.wait() with timeout for efficient CPU usage
                self.check_trigger.wait(timeout=self.stability_interval)
                self.check_trigger.clear()

                # Check all files for stability
                self.event_handler.check_all_files()

                # Reset idle counter
                consecutive_idle_checks = 0

            else:
                # Idle mode: No files to monitor
                # Use adaptive polling - increase interval when idle for longer
                if consecutive_idle_checks < max_idle_checks:
                    wait_time = idle_interval
                else:
                    # After being idle for a while, check even less frequently
                    wait_time = idle_interval * 2  # 60 seconds

                # Wait efficiently - will wake up immediately if trigger is set
                triggered = self.check_trigger.wait(timeout=wait_time)

                if triggered:
                    # New file detected, go back to active mode immediately
                    self.check_trigger.clear()
                    consecutive_idle_checks = 0
                else:
                    # No trigger, we're still idle
                    consecutive_idle_checks += 1

    def add_drive(self, mount_point: str):
        """
        Dynamically add a drive to watching.

        Args:
            mount_point: Path to drive mount point
        """
        root = Path(mount_point)
        if not root.exists():
            self.logger.warning(f"Cannot add drive, path does not exist: {mount_point}")
            return

        # Don't add if already watching
        if mount_point in self.active_watches:
            self.logger.debug(f"Already watching: {mount_point}")
            return

        try:
            # Schedule watching for this drive
            watch_handle = self.observer.schedule(self.event_handler, str(root), recursive=True)
            self.active_watches[mount_point] = watch_handle

            # Log existing audio folders
            audio_folders = self._find_audio_folders(root)
            self.logger.info(f"Now watching: {mount_point}")
            if audio_folders:
                self.logger.info(f"  Found {len(audio_folders)} Audio Files folders")

        except Exception as e:
            self.logger.error(f"Failed to add watch for {mount_point}: {e}")

    def remove_drive(self, mount_point: str):
        """
        Dynamically remove a drive from watching.

        Args:
            mount_point: Path to drive mount point
        """
        if mount_point not in self.active_watches:
            self.logger.debug(f"Not watching: {mount_point}")
            return

        try:
            # Unschedule watching for this drive
            watch_handle = self.active_watches[mount_point]
            self.observer.unschedule(watch_handle)
            del self.active_watches[mount_point]

            self.logger.info(f"Stopped watching: {mount_point}")

        except Exception as e:
            self.logger.error(f"Failed to remove watch for {mount_point}: {e}")

    def start(self):
        """Start watching for files."""
        self.logger.info("=" * 80)
        self.logger.info("Pro Tools Bounce Watcher Starting")
        self.logger.info("=" * 80)
        self.logger.info(f"Watch roots: {self.watch_roots}")
        self.logger.info(f"Source mode: {self.source_mode}")
        self.logger.info(f"Looking for files starting with: {self.mix_prefix}")
        self.logger.info(f"Destination mode: {self.destination_manager.mode}")

        # Watch each root directory
        watched_paths = []
        for root_path in self.watch_roots:
            root = Path(root_path)
            if root.exists():
                watch_handle = self.observer.schedule(self.event_handler, str(root), recursive=True)
                self.active_watches[root_path] = watch_handle
                watched_paths.append(root)
                self.logger.info(f"Watching: {root}")

                # Log existing audio folders
                audio_folders = self._find_audio_folders(root)
                if audio_folders:
                    self.logger.info(f"Found {len(audio_folders)} existing Audio Files folders")
            else:
                self.logger.warning(f"Watch root does not exist: {root_path}")

        if not watched_paths:
            raise RuntimeError("No valid watch paths found")

        # Start observer
        self.observer.start()
        self.logger.info("File system observer started")

        # Start stability check loop
        self.running = True
        self.stability_thread = threading.Thread(target=self._stability_check_loop, daemon=True)
        self.stability_thread.start()
        self.logger.info("Stability monitor started")

        # Start drive monitoring if in all_external_drives mode
        if self.source_mode == "all_external_drives" and self.source_manager:
            from .drive_monitor import DriveMonitor

            self.drive_monitor = DriveMonitor(
                self.source_manager,
                on_drive_added=self.add_drive,
                on_drive_removed=self.remove_drive
            )
            self.drive_monitor.start(current_drives=self.watch_roots)
            self.logger.info("Dynamic drive monitoring enabled")
            self.logger.info("Will automatically detect external drives being connected/disconnected")

        self.logger.info("Bounce watcher is running. Press Ctrl+C to stop.")

    def stop(self):
        """Stop watching for files."""
        self.logger.info("Stopping bounce watcher...")
        self.running = False

        # Stop drive monitoring if active
        if self.drive_monitor:
            self.drive_monitor.stop()

        self.observer.stop()
        self.observer.join()
        self.logger.info("Bounce watcher stopped")

    def run(self):
        """
        Run the watcher (blocking).

        Starts watching and blocks until interrupted with Ctrl+C.
        """
        self.start()

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()

    def _find_audio_folders(self, root_path: Path) -> list:
        """
        Find all audio files folders under root path.

        Args:
            root_path: Root path to search

        Returns:
            List of audio folder paths
        """
        audio_folders = []

        if not root_path.exists():
            return audio_folders

        try:
            for path in root_path.rglob(self.audio_folder_name):
                if path.is_dir():
                    audio_folders.append(path)
        except PermissionError as e:
            self.logger.error(f"Permission denied scanning {root_path}: {e}")
        except Exception as e:
            self.logger.error(f"Error scanning {root_path}: {e}")

        return audio_folders
