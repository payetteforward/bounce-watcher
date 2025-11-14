"""
LaunchAgent management for Bounce Watcher.

Handles macOS LaunchAgent service installation, configuration, and lifecycle.
"""

import subprocess
import plistlib
from pathlib import Path
from typing import Optional, Dict, Any


class LaunchdError(Exception):
    """Raised when LaunchAgent operations fail."""
    pass


class LaunchAgentManager:
    """
    Manages macOS LaunchAgent for Bounce Watcher.

    Handles service installation, configuration, and lifecycle management.
    """

    # LaunchAgent configuration
    LABEL = "com.payetteforward.bouncewatcher"
    PLIST_FILENAME = f"{LABEL}.plist"

    def __init__(self, script_path: Optional[Path] = None):
        """
        Initialize LaunchAgent manager.

        Args:
            script_path: Path to bounce-watcher executable. If None, uses 'bounce-watcher' in PATH.
        """
        self.label = self.LABEL
        self.plist_dir = Path.home() / "Library" / "LaunchAgents"
        self.plist_path = self.plist_dir / self.PLIST_FILENAME

        # Determine script path
        if script_path:
            self.script_path = Path(script_path)
        else:
            # Try to find bounce-watcher in PATH
            try:
                result = subprocess.run(
                    ["which", "bounce-watcher"],
                    capture_output=True,
                    text=True,
                    check=True
                )
                self.script_path = Path(result.stdout.strip())
            except subprocess.CalledProcessError:
                # Default to Python module execution
                import sys
                self.script_path = Path(sys.executable)

    def is_installed(self) -> bool:
        """
        Check if LaunchAgent is installed.

        Returns:
            True if plist file exists, False otherwise
        """
        return self.plist_path.exists()

    def is_loaded(self) -> bool:
        """
        Check if LaunchAgent is loaded (running or scheduled to run).

        Returns:
            True if service is loaded, False otherwise
        """
        try:
            result = subprocess.run(
                ["launchctl", "list"],
                capture_output=True,
                text=True,
                check=True
            )
            return self.label in result.stdout
        except subprocess.CalledProcessError:
            return False

    def get_status(self) -> Dict[str, Any]:
        """
        Get status information about the LaunchAgent.

        Returns:
            Dictionary with status information
        """
        status = {
            "installed": self.is_installed(),
            "loaded": False,
            "pid": None,
            "exit_code": None,
        }

        if not status["installed"]:
            return status

        # Check if loaded and get details
        try:
            result = subprocess.run(
                ["launchctl", "list", self.label],
                capture_output=True,
                text=True,
                check=True
            )

            status["loaded"] = True

            # Parse output for PID and status
            for line in result.stdout.splitlines():
                if '"PID"' in line:
                    try:
                        pid = int(line.split("=")[1].strip().rstrip(";"))
                        status["pid"] = pid
                    except:
                        pass
                elif '"LastExitStatus"' in line:
                    try:
                        exit_code = int(line.split("=")[1].strip().rstrip(";"))
                        status["exit_code"] = exit_code
                    except:
                        pass

        except subprocess.CalledProcessError:
            status["loaded"] = False

        return status

    def create_plist(
        self,
        working_directory: Optional[Path] = None,
        log_stdout: Optional[Path] = None,
        log_stderr: Optional[Path] = None
    ) -> None:
        """
        Create LaunchAgent plist file.

        Args:
            working_directory: Working directory for the service
            log_stdout: Path to stdout log file
            log_stderr: Path to stderr log file

        Raises:
            LaunchdError: If plist creation fails
        """
        # Ensure LaunchAgents directory exists
        self.plist_dir.mkdir(parents=True, exist_ok=True)

        # Determine working directory
        if working_directory is None:
            working_directory = Path.home() / "scripts" / "bounce-watcher"

        # Determine log paths
        if log_stdout is None:
            log_stdout = working_directory / "stdout.log"
        if log_stderr is None:
            log_stderr = working_directory / "stderr.log"

        # Build plist dictionary
        plist_dict = {
            "Label": self.label,
            "ProgramArguments": [str(self.script_path)],
            "WorkingDirectory": str(working_directory),
            "RunAtLoad": True,
            "KeepAlive": {
                "SuccessfulExit": False,  # Restart on crash, not on clean exit
            },
            "StandardOutPath": str(log_stdout),
            "StandardErrorPath": str(log_stderr),
            "ProcessType": "Background",
        }

        # Write plist file
        try:
            with open(self.plist_path, "wb") as f:
                plistlib.dump(plist_dict, f)
            print(f"Created LaunchAgent plist: {self.plist_path}")
        except Exception as e:
            raise LaunchdError(f"Failed to create plist file: {e}")

    def install(
        self,
        working_directory: Optional[Path] = None,
        log_stdout: Optional[Path] = None,
        log_stderr: Optional[Path] = None,
        load: bool = True
    ) -> None:
        """
        Install LaunchAgent.

        Creates plist file and optionally loads the service.

        Args:
            working_directory: Working directory for the service
            log_stdout: Path to stdout log file
            log_stderr: Path to stderr log file
            load: Whether to load the service after installation

        Raises:
            LaunchdError: If installation fails
        """
        # If already installed, unload first
        if self.is_installed() and self.is_loaded():
            print("Existing LaunchAgent found. Unloading...")
            self.unload()

        # Create plist
        self.create_plist(working_directory, log_stdout, log_stderr)

        # Load if requested
        if load:
            self.load()

        print(f"LaunchAgent installed: {self.label}")

    def uninstall(self) -> None:
        """
        Uninstall LaunchAgent.

        Unloads service and removes plist file.

        Raises:
            LaunchdError: If uninstallation fails
        """
        # Unload if loaded
        if self.is_loaded():
            self.unload()

        # Remove plist file
        if self.is_installed():
            try:
                self.plist_path.unlink()
                print(f"Removed LaunchAgent plist: {self.plist_path}")
            except Exception as e:
                raise LaunchdError(f"Failed to remove plist file: {e}")

        print(f"LaunchAgent uninstalled: {self.label}")

    def load(self) -> None:
        """
        Load LaunchAgent (start the service).

        Raises:
            LaunchdError: If loading fails
        """
        if not self.is_installed():
            raise LaunchdError("LaunchAgent is not installed. Install it first.")

        if self.is_loaded():
            print(f"LaunchAgent already loaded: {self.label}")
            return

        try:
            subprocess.run(
                ["launchctl", "load", str(self.plist_path)],
                capture_output=True,
                text=True,
                check=True
            )
            print(f"Loaded LaunchAgent: {self.label}")
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() if e.stderr else str(e)
            raise LaunchdError(f"Failed to load LaunchAgent: {error_msg}")

    def unload(self) -> None:
        """
        Unload LaunchAgent (stop the service).

        Raises:
            LaunchdError: If unloading fails
        """
        if not self.is_loaded():
            print(f"LaunchAgent not loaded: {self.label}")
            return

        try:
            subprocess.run(
                ["launchctl", "unload", str(self.plist_path)],
                capture_output=True,
                text=True,
                check=True
            )
            print(f"Unloaded LaunchAgent: {self.label}")
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() if e.stderr else str(e)
            raise LaunchdError(f"Failed to unload LaunchAgent: {error_msg}")

    def restart(self) -> None:
        """
        Restart LaunchAgent.

        Raises:
            LaunchdError: If restart fails
        """
        if self.is_loaded():
            self.unload()
        self.load()
        print(f"Restarted LaunchAgent: {self.label}")

    def ensure_single_instance(self) -> None:
        """
        Ensure only one instance of the LaunchAgent exists.

        Checks for and removes any duplicate or stale services.
        """
        # Check for loaded service
        if self.is_loaded():
            status = self.get_status()
            if status.get("pid"):
                print(f"LaunchAgent is running (PID: {status['pid']})")
            else:
                print(f"LaunchAgent is loaded but not running")

            # If we want to update, unload first
            print("Unloading existing service before update...")
            self.unload()

    def print_status(self) -> None:
        """Print human-readable status information."""
        status = self.get_status()

        print(f"LaunchAgent Status: {self.label}")
        print(f"  Installed: {status['installed']}")
        if status['installed']:
            print(f"  Plist path: {self.plist_path}")
        print(f"  Loaded: {status['loaded']}")
        if status['loaded']:
            if status['pid']:
                print(f"  Running: Yes (PID: {status['pid']})")
            else:
                print(f"  Running: No")
            if status['exit_code'] is not None:
                print(f"  Last exit code: {status['exit_code']}")


def get_launch_agent_manager(script_path: Optional[Path] = None) -> LaunchAgentManager:
    """
    Create and return a LaunchAgent manager.

    Args:
        script_path: Path to bounce-watcher executable

    Returns:
        LaunchAgentManager instance
    """
    return LaunchAgentManager(script_path)
