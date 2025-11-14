"""
Interactive configuration utility for Bounce Watcher.

Provides a CLI wizard for setting up Bounce Watcher configuration.
"""

import sys
import getpass
from pathlib import Path
from typing import Optional

from .config import Config, ConfigError
from .sources import SourceManager
from .destinations import (
    DestinationManager,
    set_keychain_password,
    get_keychain_password,
    KeychainError
)
from .launchd import get_launch_agent_manager, LaunchdError


def print_header(text: str):
    """Print a formatted header."""
    print("\n" + "=" * 80)
    print(text.center(80))
    print("=" * 80 + "\n")


def print_section(text: str):
    """Print a formatted section header."""
    print("\n" + "-" * 80)
    print(text)
    print("-" * 80 + "\n")


class GoBackException(Exception):
    """Raised when user wants to go back in the wizard."""
    pass


def get_input(prompt: str, default: Optional[str] = None, allow_back: bool = False) -> str:
    """
    Get user input with optional default value.

    Args:
        prompt: Prompt text
        default: Default value if user presses Enter
        allow_back: If True, allow user to type 'b' or 'back' to raise GoBackException

    Returns:
        User input or default value

    Raises:
        GoBackException: If user types 'b' or 'back' and allow_back is True
    """
    back_hint = " (or 'b' to go back)" if allow_back else ""
    if default:
        full_prompt = f"{prompt} [{default}]{back_hint}: "
    else:
        full_prompt = f"{prompt}{back_hint}: "

    value = input(full_prompt).strip()

    # Check for go back command
    if allow_back and value.lower() in ['b', 'back']:
        raise GoBackException()

    return value if value else default


def get_yes_no(prompt: str, default: bool = True) -> bool:
    """
    Get yes/no input from user.

    Args:
        prompt: Prompt text
        default: Default value if user presses Enter

    Returns:
        True for yes, False for no
    """
    default_str = "Y/n" if default else "y/N"
    value = input(f"{prompt} [{default_str}]: ").strip().lower()

    if not value:
        return default

    return value in ["y", "yes"]


def get_choice(prompt: str, choices: list, default: int = 0, allow_back: bool = False) -> int:
    """
    Get choice from a list of options.

    Args:
        prompt: Prompt text
        choices: List of choice labels
        default: Default choice index
        allow_back: If True, allow user to type 'b' or 'back' to return -1

    Returns:
        Selected choice index, or -1 if user chose to go back
    """
    print(f"\n{prompt}")
    for i, choice in enumerate(choices):
        marker = "*" if i == default else " "
        print(f"  {marker} {i + 1}. {choice}")

    back_hint = " (or 'b' to go back)" if allow_back else ""
    while True:
        value = input(f"\nEnter choice [1-{len(choices)}]{back_hint} (default: {default + 1}): ").strip().lower()

        if not value:
            return default

        # Check for go back command
        if allow_back and value in ['b', 'back']:
            return -1

        try:
            choice_num = int(value)
            if 1 <= choice_num <= len(choices):
                return choice_num - 1
            else:
                print(f"Please enter a number between 1 and {len(choices)}")
        except ValueError:
            if allow_back:
                print("Please enter a valid number or 'b' to go back")
            else:
                print("Please enter a valid number")


def configure_source() -> dict:
    """
    Configure source settings interactively.

    Returns:
        Source configuration dictionary

    Raises:
        GoBackException: If user wants to go back
    """
    print_section("SOURCE CONFIGURATION")

    # Choose mode
    mode_choice = get_choice(
        "How would you like to select source folders?",
        [
            "Specific folders (manually choose which drives/folders to watch)",
            "All external drives (automatically detect and watch all external drives)"
        ],
        default=0,
        allow_back=True
    )

    # Check if user wants to go back
    if mode_choice == -1:
        raise GoBackException()

    if mode_choice == 0:
        # Specific folders mode
        mode = "specific_folders"
        folders = []

        print("\nEnter folder paths to watch (one per line).")
        print("Press Enter on an empty line when done.")
        print("\nExamples:")
        print("  /Volumes/Great 8")
        print("  /Volumes/Crazy 8")
        print()

        while True:
            folder = input(f"Folder {len(folders) + 1} (or Enter to finish): ").strip()
            if not folder:
                if len(folders) == 0:
                    print("You must specify at least one folder.")
                    continue
                break

            folder_path = Path(folder)
            if not folder_path.exists():
                if get_yes_no(f"Warning: '{folder}' does not exist. Add anyway?", default=False):
                    folders.append(folder)
            else:
                folders.append(folder)

    else:
        # All external drives mode
        mode = "all_external_drives"
        folders = []

        # Show currently detected drives
        print("\nDetecting external drives...")
        try:
            source_mgr = SourceManager({"mode": mode})
            detected = source_mgr._detect_external_drives()
            filtered = source_mgr._apply_smart_filtering(detected)

            if filtered:
                print(f"\nFound {len(filtered)} suitable external drive(s):")
                for drive in filtered:
                    size_gb = drive.size_bytes / (1024 ** 3)
                    print(f"  - {drive.mount_point} ({drive.volume_name}, {size_gb:.1f} GB, {drive.filesystem})")
            else:
                print("\nNo suitable external drives found.")
                print("The watcher will start monitoring when drives are connected.")
        except Exception as e:
            print(f"\nWarning: Could not detect drives: {e}")

    # Audio folder name
    audio_folder = get_input(
        "\nName of the audio files folder within Pro Tools sessions",
        default="Audio Files"
    )

    # Mix file prefix
    mix_prefix = get_input(
        "Prefix for mix files to detect (case-insensitive)",
        default="mix"
    )

    return {
        "mode": mode,
        "folders": folders,
        "audio_files_folder": audio_folder,
        "mix_file_prefix": mix_prefix,
    }


def configure_destination() -> dict:
    """
    Configure destination settings interactively.

    Returns:
        Destination configuration dictionary

    Raises:
        GoBackException: If user wants to go back
    """
    print_section("DESTINATION CONFIGURATION")

    # Choose mode
    mode_choice = get_choice(
        "Where would you like to save converted files?",
        [
            "iCloud Downloads folder",
            "Network storage (NAS via SMB)",
            "Custom folder"
        ],
        default=0,
        allow_back=True
    )

    # Check if user wants to go back
    if mode_choice == -1:
        raise GoBackException()

    if mode_choice == 0:
        # iCloud mode
        mode = "icloud"
        default_icloud = str(Path.home() / "Library" / "Mobile Documents" / "com~apple~CloudDocs" / "Downloads")
        icloud_path = get_input(
            "\nPath to iCloud Downloads folder",
            default=default_icloud
        )

        # Verify path exists
        if not Path(icloud_path).exists():
            print(f"Warning: Path does not exist: {icloud_path}")
            print("Make sure iCloud Drive is enabled and syncing.")

        return {
            "mode": mode,
            "icloud_path": icloud_path,
            "nas_url": "smb://your-nas-server.local/share",
            "nas_username": "your-username",
            "nas_mount_point": "/Volumes/NAS",
            "custom_path": str(Path.home() / "Music" / "Bounce Watcher"),
        }

    elif mode_choice == 1:
        # NAS mode
        mode = "nas"

        nas_url = get_input(
            "\nNAS URL (SMB)",
            default="smb://your-nas-server.local/share"
        )

        nas_username = get_input(
            "NAS username",
            default="your-username"
        )

        nas_mount_point = get_input(
            "Local mount point for NAS",
            default="/Volumes/NAS"
        )

        # Prompt for password and store in keychain
        print("\nNAS password will be stored securely in macOS Keychain.")

        # Check if password already exists
        server = nas_url.replace("smb://", "").split("/")[0]
        try:
            existing_password = get_keychain_password(nas_username, server)
            if existing_password:
                if get_yes_no(f"Password already exists in keychain for {nas_username}@{server}. Update?", default=False):
                    password = getpass.getpass("Enter NAS password: ")
                    if password:
                        set_keychain_password(nas_username, server, password)
                        print("Password updated in keychain.")
        except KeychainError:
            # No existing password
            password = getpass.getpass("Enter NAS password: ")
            if password:
                set_keychain_password(nas_username, server, password)
                print("Password stored in keychain.")
            else:
                print("Warning: No password provided. You'll need to add it to keychain manually.")

        # Test NAS connection
        if get_yes_no("\nTest NAS connection now?", default=True):
            print("Testing NAS connection...")
            try:
                dest_mgr = DestinationManager({
                    "mode": mode,
                    "nas_url": nas_url,
                    "nas_username": nas_username,
                    "nas_mount_point": nas_mount_point,
                })
                if dest_mgr.test_destination():
                    print("✓ NAS connection successful!")
                else:
                    print("✗ NAS connection failed. Please check your settings.")
            except Exception as e:
                print(f"✗ NAS connection failed: {e}")

        return {
            "mode": mode,
            "icloud_path": str(Path.home() / "Library" / "Mobile Documents" / "com~apple~CloudDocs" / "Downloads"),
            "nas_url": nas_url,
            "nas_username": nas_username,
            "nas_mount_point": nas_mount_point,
            "custom_path": str(Path.home() / "Music" / "Bounce Watcher"),
        }

    else:
        # Custom folder mode
        mode = "custom"

        default_custom = str(Path.home() / "Music" / "Bounce Watcher")
        custom_path = get_input(
            "\nCustom folder path (where converted files will be saved)",
            default=default_custom
        )

        # Verify/create path
        custom_path_obj = Path(custom_path)
        if not custom_path_obj.exists():
            if get_yes_no(f"\nFolder does not exist. Create it?", default=True):
                try:
                    custom_path_obj.mkdir(parents=True, exist_ok=True)
                    print(f"✓ Created folder: {custom_path}")
                except Exception as e:
                    print(f"✗ Failed to create folder: {e}")
            else:
                print("Warning: Folder will need to exist before saving files.")
        else:
            print(f"✓ Folder exists: {custom_path}")

        return {
            "mode": mode,
            "icloud_path": str(Path.home() / "Library" / "Mobile Documents" / "com~apple~CloudDocs" / "Downloads"),
            "nas_url": "smb://your-nas-server.local/share",
            "nas_username": "your-username",
            "nas_mount_point": "/Volumes/NAS",
            "custom_path": custom_path,
        }


def configure_conversion() -> dict:
    """
    Configure conversion settings interactively.

    Returns:
        Conversion configuration dictionary

    Raises:
        GoBackException: If user wants to go back
    """
    print_section("CONVERSION SETTINGS")

    sample_rate = get_input(
        "Target sample rate (Hz)",
        default="48000",
        allow_back=True
    )

    try:
        sample_rate = int(sample_rate)
    except ValueError:
        print("Invalid sample rate, using default 48000")
        sample_rate = 48000

    stability_interval = get_input(
        "Stability check interval (seconds)",
        default="2"
    )

    try:
        stability_interval = int(stability_interval)
    except ValueError:
        stability_interval = 2

    stability_checks = get_input(
        "Number of stability checks required",
        default="3"
    )

    try:
        stability_checks = int(stability_checks)
    except ValueError:
        stability_checks = 3

    return {
        "sample_rate": sample_rate,
        "stability_check_interval": stability_interval,
        "stability_checks_required": stability_checks,
    }


def configure_logging() -> dict:
    """
    Configure logging settings interactively.

    Returns:
        Logging configuration dictionary

    Raises:
        GoBackException: If user wants to go back
    """
    print_section("LOGGING SETTINGS")

    default_log = str(Path.home() / "scripts" / "bounce-watcher" / "bounce_watcher.log")
    log_file = get_input(
        "Log file path",
        default=default_log,
        allow_back=True
    )

    log_level = get_choice(
        "Log level",
        ["DEBUG (verbose)", "INFO (normal)", "WARNING (errors only)"],
        default=1,
        allow_back=True
    )

    # Check if user wants to go back
    if log_level == -1:
        raise GoBackException()

    level_map = {0: "DEBUG", 1: "INFO", 2: "WARNING"}

    return {
        "log_file": log_file,
        "level": level_map[log_level],
    }


def configure_launchagent(config_path: Path):
    """
    Configure LaunchAgent service.

    Args:
        config_path: Path to configuration file
    """
    print_section("LAUNCHAGENT SETUP")

    launch_mgr = get_launch_agent_manager()

    # Check current status
    status = launch_mgr.get_status()
    if status["installed"]:
        print(f"LaunchAgent is currently installed.")
        if status["loaded"]:
            if status.get("pid"):
                print(f"Service is running (PID: {status['pid']})")
            else:
                print(f"Service is loaded but not running")
    else:
        print("LaunchAgent is not currently installed.")

    print("\nThe LaunchAgent will:")
    print("  - Start Bounce Watcher automatically when you log in")
    print("  - Restart it automatically if it crashes")
    print("  - Run in the background")

    if not get_yes_no("\nInstall/update LaunchAgent?", default=True):
        return

    # Determine paths
    working_dir = config_path.parent
    log_stdout = working_dir / "stdout.log"
    log_stderr = working_dir / "stderr.log"

    try:
        # Ensure single instance
        launch_mgr.ensure_single_instance()

        # Install
        launch_mgr.install(
            working_directory=working_dir,
            log_stdout=log_stdout,
            log_stderr=log_stderr,
            load=True
        )

        print("\n✓ LaunchAgent installed and started successfully!")
        print(f"\nLogs will be written to:")
        print(f"  stdout: {log_stdout}")
        print(f"  stderr: {log_stderr}")

    except LaunchdError as e:
        print(f"\n✗ Failed to install LaunchAgent: {e}")


def run_interactive_wizard():
    """Run the full interactive configuration wizard with go-back support."""
    print_header("BOUNCE WATCHER CONFIGURATION WIZARD")

    print("This wizard will help you set up Bounce Watcher.")
    print("\nYou can reconfigure at any time by running 'bounce-config' again.")
    print("Type 'b' or 'back' at any prompt to go to the previous step.")

    if not get_yes_no("\nContinue?", default=True):
        print("Configuration cancelled.")
        sys.exit(0)

    # Configuration steps as a state machine
    steps = [
        ("source", "Source Configuration", configure_source),
        ("destination", "Destination Configuration", configure_destination),
        ("conversion", "Conversion Settings", configure_conversion),
        ("logging", "Logging Settings", configure_logging),
    ]

    config_dict = {}
    current_step = 0

    # Navigate through configuration steps
    while current_step < len(steps):
        step_key, step_title, step_func = steps[current_step]

        try:
            # Run configuration step
            config_dict[step_key] = step_func()
            # Move to next step on success
            current_step += 1

        except GoBackException:
            # User wants to go back
            if current_step > 0:
                current_step -= 1
                print(f"\n⬅ Going back to {steps[current_step][1]}...")
            else:
                print("\nAlready at first step!")

    # Save configuration
    print_section("SAVING CONFIGURATION")

    config = Config()
    config.config = config_dict

    try:
        config.save()
        print(f"✓ Configuration saved to: {config.config_path}")
    except ConfigError as e:
        print(f"✗ Failed to save configuration: {e}")
        sys.exit(1)

    # Configure LaunchAgent
    configure_launchagent(config.config_path)

    # Done
    print_header("CONFIGURATION COMPLETE")
    print("Bounce Watcher is now configured and running!")
    print("\nUseful commands:")
    print("  bounce-config --status    Show current status")
    print("  bounce-config --test      Test configuration")
    print("  launchctl list | grep bounce    Check if service is running")
    print()


def show_status():
    """Show current configuration and service status."""
    print_header("BOUNCE WATCHER STATUS")

    # Check configuration
    config = Config()
    if not config.exists():
        print("✗ Configuration file not found.")
        print(f"  Expected location: {config.config_path}")
        print("\nRun 'bounce-config' to create configuration.")
        return

    print(f"✓ Configuration file: {config.config_path}")

    try:
        config.load()
        print(f"  Source mode: {config.config['source']['mode']}")
        print(f"  Destination mode: {config.config['destination']['mode']}")
    except Exception as e:
        print(f"✗ Error loading configuration: {e}")
        return

    # Check LaunchAgent
    print()
    launch_mgr = get_launch_agent_manager()
    launch_mgr.print_status()


def test_configuration():
    """Test current configuration."""
    print_header("TESTING CONFIGURATION")

    config = Config()
    if not config.exists():
        print("✗ Configuration file not found.")
        return

    try:
        config.load()
        print("✓ Configuration file is valid")
    except ConfigError as e:
        print(f"✗ Configuration is invalid: {e}")
        return

    # Test source
    print("\nTesting source configuration...")
    try:
        from .sources import get_source_manager
        source_mgr = get_source_manager(config.config)
        watch_roots = source_mgr.get_watch_roots()
        print(f"✓ Found {len(watch_roots)} watch root(s)")
        for root in watch_roots:
            print(f"  - {root}")
    except Exception as e:
        print(f"✗ Source configuration failed: {e}")

    # Test destination
    print("\nTesting destination configuration...")
    try:
        from .destinations import get_destination_manager
        dest_mgr = get_destination_manager(config.config)
        if dest_mgr.test_destination():
            print("✓ Destination is accessible")
        else:
            print("✗ Destination is not accessible")
    except Exception as e:
        print(f"✗ Destination configuration failed: {e}")


def main():
    """Main entry point for bounce-config utility."""
    # Parse command line arguments
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        if arg in ["--status", "-s"]:
            show_status()
            return
        elif arg in ["--test", "-t"]:
            test_configuration()
            return
        elif arg in ["--help", "-h"]:
            print("Bounce Watcher Configuration Utility")
            print("\nUsage:")
            print("  bounce-config              Run interactive configuration wizard")
            print("  bounce-config --status     Show current status")
            print("  bounce-config --test       Test current configuration")
            print("  bounce-config --help       Show this help message")
            return
        else:
            print(f"Unknown option: {arg}")
            print("Run 'bounce-config --help' for usage information.")
            sys.exit(1)

    # Run interactive wizard
    run_interactive_wizard()


if __name__ == "__main__":
    main()
