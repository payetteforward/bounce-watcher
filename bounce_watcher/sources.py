"""
Source management for Bounce Watcher.

Handles detection and management of source folders including external drive
discovery with smart filtering.
"""

import subprocess
import plistlib
import re
from pathlib import Path
from typing import List, Set, Dict, Any
from dataclasses import dataclass


@dataclass
class DriveInfo:
    """Information about a detected drive."""
    mount_point: str
    device: str
    filesystem: str
    volume_name: str
    size_bytes: int
    is_external: bool


class SourceManager:
    """
    Manages source folders for file watching.

    Supports both specific folder mode and automatic external drive detection.
    """

    # Minimum drive size to consider (1 GB in bytes)
    MIN_DRIVE_SIZE = 1 * 1024 * 1024 * 1024

    # Filesystems to include in smart filtering
    ALLOWED_FILESYSTEMS = {"apfs", "hfs", "hfsx", "jhfs+", "jhfsx"}

    # Patterns to exclude from auto-detection
    EXCLUDE_PATTERNS = [
        r"Time Machine",
        r"\.timemachine",
        r"Backups\.backupdb",
        r"^\.Trash",
        r"^\.Spotlight",
        r"^\.fseventsd",
    ]

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize source manager.

        Args:
            config: Configuration dictionary with source settings
        """
        self.config = config
        self.mode = config.get("mode", "specific_folders")
        self.folders = config.get("folders", [])
        self.audio_files_folder = config.get("audio_files_folder", "Audio Files")

    def get_watch_roots(self) -> List[str]:
        """
        Get list of root directories to watch.

        Returns:
            List of absolute paths to watch

        Raises:
            RuntimeError: If no valid watch roots found
        """
        if self.mode == "specific_folders":
            return self._get_specific_folders()
        elif self.mode == "all_external_drives":
            return self._get_external_drives()
        else:
            raise ValueError(f"Invalid source mode: {self.mode}")

    def _get_specific_folders(self) -> List[str]:
        """
        Get specific folders from configuration.

        Returns:
            List of configured folder paths

        Raises:
            RuntimeError: If no folders configured or none exist
        """
        if not self.folders:
            raise RuntimeError("No folders configured in specific_folders mode")

        valid_folders = []
        for folder in self.folders:
            path = Path(folder)
            if path.exists() and path.is_dir():
                valid_folders.append(str(path.absolute()))
            else:
                print(f"Warning: Configured folder does not exist: {folder}")

        if not valid_folders:
            raise RuntimeError("None of the configured folders exist")

        return valid_folders

    def _get_external_drives(self) -> List[str]:
        """
        Get all external drives with smart filtering.

        Returns:
            List of external drive mount points

        Raises:
            RuntimeError: If no external drives found
        """
        drives = self._detect_external_drives()
        filtered_drives = self._apply_smart_filtering(drives)

        if not filtered_drives:
            raise RuntimeError("No suitable external drives found")

        return [drive.mount_point for drive in filtered_drives]

    def _detect_external_drives(self) -> List[DriveInfo]:
        """
        Detect all mounted external drives using diskutil.

        Returns:
            List of DriveInfo objects for external drives
        """
        drives = []
        volumes_path = Path("/Volumes")

        if not volumes_path.exists():
            print("Warning: /Volumes directory not found")
            return []

        # Iterate through all mounted volumes
        try:
            for volume_path in volumes_path.iterdir():
                if not volume_path.is_dir():
                    continue

                # Skip hidden volumes
                if volume_path.name.startswith('.'):
                    continue

                mount_point = str(volume_path)

                # Get volume info using diskutil
                try:
                    result = subprocess.run(
                        ["diskutil", "info", "-plist", mount_point],
                        capture_output=True,
                        check=True
                    )
                    volume_info = plistlib.loads(result.stdout)
                except subprocess.CalledProcessError:
                    # Volume might have been unmounted or is inaccessible
                    continue
                except Exception as e:
                    print(f"Warning: Error getting info for {mount_point}: {e}")
                    continue

                # Check if this is an external drive
                # Use RemovableMediaOrExternalDevice as primary check, fall back to Internal flag
                is_external = (
                    volume_info.get("RemovableMediaOrExternalDevice", False) or
                    volume_info.get("Internal", True) == False
                )

                if not is_external:
                    continue

                # Get volume details
                device = volume_info.get("DeviceIdentifier", "")
                volume_name = volume_info.get("VolumeName", volume_path.name)
                filesystem = volume_info.get("FilesystemType", "").lower()
                size_bytes = volume_info.get("TotalSize", 0)

                drive_info = DriveInfo(
                    mount_point=mount_point,
                    device=device,
                    filesystem=filesystem,
                    volume_name=volume_name,
                    size_bytes=size_bytes,
                    is_external=is_external
                )

                drives.append(drive_info)

        except Exception as e:
            print(f"Warning: Error scanning /Volumes: {e}")

        return drives

    def _apply_smart_filtering(self, drives: List[DriveInfo]) -> List[DriveInfo]:
        """
        Apply smart filtering to drives.

        Filters out:
        - Drives smaller than MIN_DRIVE_SIZE
        - Non-APFS/HFS+ filesystems
        - Time Machine volumes
        - System volumes

        Args:
            drives: List of DriveInfo objects

        Returns:
            Filtered list of DriveInfo objects
        """
        filtered = []

        for drive in drives:
            # Check filesystem
            if drive.filesystem not in self.ALLOWED_FILESYSTEMS:
                print(f"Excluding {drive.mount_point}: unsupported filesystem ({drive.filesystem})")
                continue

            # Check size
            if drive.size_bytes < self.MIN_DRIVE_SIZE:
                size_mb = drive.size_bytes / (1024 * 1024)
                print(f"Excluding {drive.mount_point}: too small ({size_mb:.1f} MB)")
                continue

            # Check exclude patterns
            excluded = False
            for pattern in self.EXCLUDE_PATTERNS:
                if re.search(pattern, drive.mount_point, re.IGNORECASE):
                    print(f"Excluding {drive.mount_point}: matches exclusion pattern '{pattern}'")
                    excluded = True
                    break
                if re.search(pattern, drive.volume_name, re.IGNORECASE):
                    print(f"Excluding {drive.mount_point}: volume name matches exclusion pattern '{pattern}'")
                    excluded = True
                    break

            if excluded:
                continue

            filtered.append(drive)

        return filtered

    def find_audio_folders(self, root: str) -> List[str]:
        """
        Find all audio files folders under a root directory.

        Args:
            root: Root directory to search

        Returns:
            List of paths to audio files folders
        """
        audio_folders = []
        root_path = Path(root)

        if not root_path.exists():
            return []

        # Search recursively for folders matching the audio files folder name
        for audio_folder in root_path.rglob(self.audio_files_folder):
            if audio_folder.is_dir():
                audio_folders.append(str(audio_folder.absolute()))

        return audio_folders

    def get_all_audio_folders(self) -> List[str]:
        """
        Get all audio folders from all watch roots.

        Returns:
            List of all audio folder paths
        """
        all_folders = []
        watch_roots = self.get_watch_roots()

        for root in watch_roots:
            folders = self.find_audio_folders(root)
            all_folders.extend(folders)

        return all_folders

    def __repr__(self) -> str:
        """String representation of source manager."""
        return f"SourceManager(mode={self.mode}, folders={len(self.folders)})"


def get_source_manager(config: Dict[str, Any]) -> SourceManager:
    """
    Create and return a source manager from configuration.

    Args:
        config: Configuration dictionary

    Returns:
        Configured SourceManager instance
    """
    source_config = config.get("source", {})
    return SourceManager(source_config)
