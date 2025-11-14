"""
Dynamic drive monitoring for Bounce Watcher.

Monitors for external drives being connected/disconnected and dynamically
updates the file watching.
"""

import logging
import time
from pathlib import Path
from typing import Set, Callable, Optional
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, DirCreatedEvent, DirDeletedEvent

from .sources import SourceManager, DriveInfo
from .utils import send_notification


class DriveEventHandler(FileSystemEventHandler):
    """
    Handles drive mount/unmount events in /Volumes.

    Monitors the /Volumes directory and triggers callbacks when external
    drives are connected or disconnected.
    """

    def __init__(
        self,
        source_manager: SourceManager,
        on_drive_added: Callable[[str], None],
        on_drive_removed: Callable[[str], None]
    ):
        """
        Initialize drive event handler.

        Args:
            source_manager: SourceManager for drive detection and filtering
            on_drive_added: Callback when a new drive is added (receives mount point)
            on_drive_removed: Callback when a drive is removed (receives mount point)
        """
        super().__init__()
        self.source_manager = source_manager
        self.on_drive_added = on_drive_added
        self.on_drive_removed = on_drive_removed
        self.logger = logging.getLogger("bounce_watcher.drive_monitor")
        self.monitored_drives: Set[str] = set()

    def on_created(self, event):
        """
        Handle directory creation in /Volumes (drive mounted).

        Args:
            event: File system event
        """
        if not isinstance(event, DirCreatedEvent):
            return

        mount_point = event.src_path

        # Skip hidden directories
        if Path(mount_point).name.startswith('.'):
            return

        # Give the system a moment to finish mounting
        time.sleep(1)

        # Check if this is a valid external drive
        if self._is_valid_external_drive(mount_point):
            self.logger.info(f"New external drive detected: {mount_point}")
            self.monitored_drives.add(mount_point)

            # Notify user
            drive_name = Path(mount_point).name
            send_notification(
                "Bounce Watcher",
                f"Now monitoring: {drive_name}",
                subtitle="External drive connected"
            )

            # Trigger callback
            self.on_drive_added(mount_point)

    def on_deleted(self, event):
        """
        Handle directory deletion in /Volumes (drive unmounted).

        Args:
            event: File system event
        """
        if not isinstance(event, DirDeletedEvent):
            return

        mount_point = event.src_path

        # Only process if we were monitoring this drive
        if mount_point in self.monitored_drives:
            self.logger.info(f"External drive disconnected: {mount_point}")
            self.monitored_drives.remove(mount_point)

            # Notify user
            drive_name = Path(mount_point).name
            send_notification(
                "Bounce Watcher",
                f"Stopped monitoring: {drive_name}",
                subtitle="External drive disconnected"
            )

            # Trigger callback
            self.on_drive_removed(mount_point)

    def _is_valid_external_drive(self, mount_point: str) -> bool:
        """
        Check if a mount point is a valid external drive.

        Args:
            mount_point: Path to check

        Returns:
            True if valid external drive, False otherwise
        """
        if not Path(mount_point).exists():
            return False

        # Detect all drives and find this one
        drives = self.source_manager._detect_external_drives()

        for drive in drives:
            if drive.mount_point == mount_point:
                # Apply smart filtering
                filtered = self.source_manager._apply_smart_filtering([drive])
                return len(filtered) > 0

        return False

    def initialize_monitored_drives(self, current_drives: list):
        """
        Initialize the set of currently monitored drives.

        Args:
            current_drives: List of currently mounted drive paths
        """
        self.monitored_drives = set(current_drives)
        self.logger.info(f"Initialized with {len(current_drives)} drive(s)")


class DriveMonitor:
    """
    Monitors /Volumes directory for external drives being connected/disconnected.

    Provides dynamic drive detection and notification for hot-plugging.
    """

    def __init__(
        self,
        source_manager: SourceManager,
        on_drive_added: Callable[[str], None],
        on_drive_removed: Callable[[str], None]
    ):
        """
        Initialize drive monitor.

        Args:
            source_manager: SourceManager for drive detection and filtering
            on_drive_added: Callback when a new drive is added
            on_drive_removed: Callback when a drive is removed
        """
        self.source_manager = source_manager
        self.on_drive_added = on_drive_added
        self.on_drive_removed = on_drive_removed
        self.logger = logging.getLogger("bounce_watcher.drive_monitor")

        # Create event handler
        self.event_handler = DriveEventHandler(
            source_manager,
            on_drive_added,
            on_drive_removed
        )

        # Create observer for /Volumes
        self.observer = Observer()
        self.running = False

    def start(self, current_drives: Optional[list] = None):
        """
        Start monitoring for drive changes.

        Args:
            current_drives: Optional list of currently mounted drives to track
        """
        volumes_path = "/Volumes"

        if not Path(volumes_path).exists():
            self.logger.warning(f"Cannot monitor drives: {volumes_path} not found")
            return

        # Initialize with current drives
        if current_drives:
            self.event_handler.initialize_monitored_drives(current_drives)

        # Start observing /Volumes
        self.observer.schedule(self.event_handler, volumes_path, recursive=False)
        self.observer.start()
        self.running = True

        self.logger.info("Drive monitoring started")
        self.logger.info(f"Watching for drive connect/disconnect events in {volumes_path}")

    def stop(self):
        """Stop monitoring for drive changes."""
        if self.running:
            self.observer.stop()
            self.observer.join()
            self.running = False
            self.logger.info("Drive monitoring stopped")

    def __repr__(self) -> str:
        """String representation of drive monitor."""
        status = "running" if self.running else "stopped"
        return f"DriveMonitor(status={status}, drives={len(self.event_handler.monitored_drives)})"
