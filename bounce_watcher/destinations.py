"""
Destination management for Bounce Watcher.

Handles iCloud and NAS destinations, including SMB mounting with keychain
authentication.
"""

import subprocess
import os
from pathlib import Path
from typing import Dict, Any, Optional
from urllib.parse import urlparse


class DestinationError(Exception):
    """Raised when destination operations fail."""
    pass


class KeychainError(Exception):
    """Raised when keychain operations fail."""
    pass


class DestinationManager:
    """
    Manages output destinations for converted files.

    Supports iCloud Downloads and NAS (SMB) destinations.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize destination manager.

        Args:
            config: Configuration dictionary with destination settings
        """
        self.config = config
        self.mode = config.get("mode", "icloud")

        # iCloud settings
        self.icloud_path = config.get("icloud_path", "")

        # NAS settings
        self.nas_url = config.get("nas_url", "")
        self.nas_username = config.get("nas_username", "")
        self.nas_mount_point = config.get("nas_mount_point", "")

        # Custom folder settings
        self.custom_path = config.get("custom_path", "")

    def get_destination_path(self, session_name: str) -> str:
        """
        Get destination path for a given session.

        Args:
            session_name: Name of the Pro Tools session

        Returns:
            Absolute path to destination directory

        Raises:
            DestinationError: If destination is not available
        """
        if self.mode == "icloud":
            return self._get_icloud_destination(session_name)
        elif self.mode == "nas":
            return self._get_nas_destination(session_name)
        elif self.mode == "custom":
            return self._get_custom_destination(session_name)
        else:
            raise DestinationError(f"Invalid destination mode: {self.mode}")

    def _get_icloud_destination(self, session_name: str) -> str:
        """
        Get iCloud destination path.

        Args:
            session_name: Name of the Pro Tools session

        Returns:
            Path to iCloud Downloads session folder

        Raises:
            DestinationError: If iCloud path is invalid or not accessible
        """
        if not self.icloud_path:
            raise DestinationError("iCloud path not configured")

        icloud_path = Path(self.icloud_path)
        if not icloud_path.exists():
            raise DestinationError(f"iCloud path does not exist: {self.icloud_path}")

        session_folder = icloud_path / session_name
        session_folder.mkdir(exist_ok=True)

        return str(session_folder.absolute())

    def _get_custom_destination(self, session_name: str) -> str:
        """
        Get custom folder destination path.

        Args:
            session_name: Name of the Pro Tools session

        Returns:
            Path to custom folder session folder

        Raises:
            DestinationError: If custom path is invalid or not accessible
        """
        if not self.custom_path:
            raise DestinationError("Custom path not configured")

        custom_path = Path(self.custom_path)
        if not custom_path.exists():
            raise DestinationError(f"Custom path does not exist: {self.custom_path}")

        if not custom_path.is_dir():
            raise DestinationError(f"Custom path is not a directory: {self.custom_path}")

        session_folder = custom_path / session_name
        session_folder.mkdir(exist_ok=True)

        return str(session_folder.absolute())

    def _get_nas_destination(self, session_name: str) -> str:
        """
        Get NAS destination path.

        Ensures NAS is mounted before returning path.

        Args:
            session_name: Name of the Pro Tools session

        Returns:
            Path to NAS session folder

        Raises:
            DestinationError: If NAS cannot be mounted or accessed
        """
        # Ensure NAS is mounted (this will update nas_mount_point if needed)
        self.ensure_nas_mounted()

        if not self.nas_mount_point:
            raise DestinationError("NAS mount point not found after mounting")

        mount_path = Path(self.nas_mount_point)
        if not mount_path.exists():
            raise DestinationError(f"NAS mount point does not exist: {self.nas_mount_point}")

        session_folder = mount_path / session_name
        session_folder.mkdir(exist_ok=True)

        return str(session_folder.absolute())

    def is_nas_mounted(self) -> bool:
        """
        Check if NAS is currently mounted.

        Returns:
            True if NAS is mounted, False otherwise
        """
        if not self.nas_url:
            return False

        # Parse the NAS URL to get the share name
        parsed = urlparse(self.nas_url)
        server = parsed.netloc
        share = parsed.path.lstrip("/")

        # Check mount output for the server/share
        try:
            result = subprocess.run(
                ["mount"],
                capture_output=True,
                text=True,
                check=True
            )

            # Look for the server in mount output
            # Mount output will show something like: //username@server.local/share on /Volumes/share
            for line in result.stdout.splitlines():
                if server in line and share in line.lower():
                    # Extract the actual mount point from the line
                    # Format: "//user@server/share on /mount/point (smbfs, ...)"
                    if " on " in line:
                        parts = line.split(" on ")
                        if len(parts) >= 2:
                            mount_point = parts[1].split(" (")[0].strip()
                            # Update our mount point to match reality
                            self.nas_mount_point = mount_point
                            return True

            # Also check if our configured mount point exists
            if self.nas_mount_point:
                mount_path = Path(self.nas_mount_point)
                if mount_path.exists() and str(mount_path) in result.stdout:
                    return True

            return False

        except subprocess.CalledProcessError:
            return False

    def ensure_nas_mounted(self) -> None:
        """
        Ensure NAS is mounted, mounting if necessary.

        Raises:
            DestinationError: If NAS cannot be mounted
        """
        if self.is_nas_mounted():
            return

        print(f"Mounting NAS at {self.nas_mount_point}...")
        self.mount_nas()

    def mount_nas(self) -> None:
        """
        Mount NAS using SMB with keychain authentication.

        Uses macOS native mounting via osascript to avoid permission issues
        with creating mount points in /Volumes.

        Raises:
            DestinationError: If mounting fails
        """
        if not self.nas_url:
            raise DestinationError("NAS URL not configured")
        if not self.nas_username:
            raise DestinationError("NAS username not configured")
        if not self.nas_mount_point:
            raise DestinationError("NAS mount point not configured")

        # Parse NAS URL to get server and share
        parsed = urlparse(self.nas_url)
        if parsed.scheme != "smb":
            raise DestinationError(f"Invalid NAS URL scheme: {parsed.scheme} (expected 'smb')")

        server = parsed.netloc
        share = parsed.path.lstrip("/")

        if not server:
            raise DestinationError(f"Invalid NAS URL: {self.nas_url}")

        # Get password from keychain
        try:
            password = get_keychain_password(self.nas_username, server)
        except KeychainError as e:
            raise DestinationError(f"Failed to get NAS password from keychain: {e}")

        # Build SMB URL with credentials
        if share:
            smb_url = f"smb://{self.nas_username}:{password}@{server}/{share}"
        else:
            smb_url = f"smb://{self.nas_username}:{password}@{server}"

        # Use osascript to mount via Finder, which handles mount point creation
        # This is the macOS-native way and doesn't require sudo
        applescript = f'''
        tell application "Finder"
            try
                mount volume "{smb_url}"
            on error errMsg
                error errMsg
            end try
        end tell
        '''

        try:
            result = subprocess.run(
                ["osascript", "-e", applescript],
                capture_output=True,
                text=True,
                check=True,
                timeout=30
            )

            # Wait a moment for mount to complete
            import time
            time.sleep(2)

            # Verify it mounted
            if not self.is_nas_mounted():
                raise DestinationError("Mount command succeeded but NAS is not accessible")

            print(f"Successfully mounted NAS at {self.nas_mount_point}")

        except subprocess.TimeoutExpired:
            raise DestinationError("Mount operation timed out")
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() if e.stderr else str(e)
            # Clean up password from error message for security
            error_msg = error_msg.replace(password, "***")
            raise DestinationError(f"Failed to mount NAS: {error_msg}")

    def unmount_nas(self) -> None:
        """
        Unmount NAS.

        Raises:
            DestinationError: If unmounting fails
        """
        if not self.is_nas_mounted():
            return

        try:
            subprocess.run(
                ["umount", self.nas_mount_point],
                capture_output=True,
                text=True,
                check=True
            )
            print(f"Successfully unmounted NAS from {self.nas_mount_point}")
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() if e.stderr else str(e)
            raise DestinationError(f"Failed to unmount NAS: {error_msg}")

    def test_destination(self) -> bool:
        """
        Test if destination is accessible.

        Returns:
            True if destination is accessible, False otherwise
        """
        try:
            if self.mode == "icloud":
                path = Path(self.icloud_path)
                return path.exists() and path.is_dir() and os.access(path, os.W_OK)
            elif self.mode == "nas":
                self.ensure_nas_mounted()
                path = Path(self.nas_mount_point)
                return path.exists() and path.is_dir() and os.access(path, os.W_OK)
            elif self.mode == "custom":
                path = Path(self.custom_path)
                return path.exists() and path.is_dir() and os.access(path, os.W_OK)
            return False
        except Exception as e:
            print(f"Destination test failed: {e}")
            return False

    def __repr__(self) -> str:
        """String representation of destination manager."""
        return f"DestinationManager(mode={self.mode})"


def get_keychain_password(account: str, server: str) -> str:
    """
    Retrieve password from macOS keychain.

    Args:
        account: Account/username
        server: Server name

    Returns:
        Password string

    Raises:
        KeychainError: If password cannot be retrieved
    """
    try:
        result = subprocess.run(
            [
                "security",
                "find-generic-password",
                "-a", account,
                "-s", server,
                "-w"  # Output password only
            ],
            capture_output=True,
            text=True,
            check=True
        )
        password = result.stdout.strip()
        if not password:
            raise KeychainError("Password is empty")
        return password
    except subprocess.CalledProcessError as e:
        if "password could not be found" in e.stderr.lower():
            raise KeychainError(f"No password found in keychain for {account}@{server}")
        else:
            raise KeychainError(f"Failed to retrieve password: {e.stderr.strip()}")


def set_keychain_password(account: str, server: str, password: str) -> None:
    """
    Store password in macOS keychain.

    Args:
        account: Account/username
        server: Server name
        password: Password to store

    Raises:
        KeychainError: If password cannot be stored
    """
    try:
        # Use -U to update if exists, otherwise create
        subprocess.run(
            [
                "security",
                "add-generic-password",
                "-a", account,
                "-s", server,
                "-w", password,
                "-U"  # Update if exists
            ],
            capture_output=True,
            text=True,
            check=True
        )
    except subprocess.CalledProcessError as e:
        raise KeychainError(f"Failed to store password: {e.stderr.strip()}")


def delete_keychain_password(account: str, server: str) -> None:
    """
    Delete password from macOS keychain.

    Args:
        account: Account/username
        server: Server name

    Raises:
        KeychainError: If password cannot be deleted
    """
    try:
        subprocess.run(
            [
                "security",
                "delete-generic-password",
                "-a", account,
                "-s", server
            ],
            capture_output=True,
            text=True,
            check=True
        )
    except subprocess.CalledProcessError as e:
        if "password could not be found" not in e.stderr.lower():
            raise KeychainError(f"Failed to delete password: {e.stderr.strip()}")


def get_destination_manager(config: Dict[str, Any]) -> DestinationManager:
    """
    Create and return a destination manager from configuration.

    Args:
        config: Configuration dictionary

    Returns:
        Configured DestinationManager instance
    """
    dest_config = config.get("destination", {})
    return DestinationManager(dest_config)
