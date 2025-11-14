"""
Interactive configuration utility for Bounce Watcher.

Provides a CLI wizard for setting up Bounce Watcher configuration.
"""

import sys
import subprocess
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


def select_sections_to_configure() -> list:
    """
    Let user select which sections to configure.

    Returns:
        List of section keys to configure
    """
    config = Config()
    existing_config = config.exists()

    if not existing_config:
        # No existing config, must configure everything
        return ["source", "destination", "conversion", "logging"]

    # Load existing config to show current values
    try:
        config.load()
    except ConfigError:
        # Config exists but is invalid, reconfigure everything
        return ["source", "destination", "conversion", "logging"]

    print_section("SELECTIVE CONFIGURATION")
    print("You have an existing configuration. You can:")
    print("  1. Reconfigure everything (fresh start)")
    print("  2. Edit specific sections only (keep other settings)")
    print()

    choice = get_choice(
        "What would you like to do?",
        [
            "Reconfigure everything",
            "Edit specific sections"
        ],
        default=1
    )

    if choice == 0:
        # Reconfigure everything
        return ["source", "destination", "conversion", "logging"]

    # Let user select sections
    print("\nSelect which sections you want to reconfigure:")
    print("(Your current settings will be preserved for unselected sections)")
    print()

    # Show current config summary
    print("Current configuration:")
    if "source" in config.config:
        mode = config.config["source"].get("mode", "unknown")
        print(f"  Source: {mode}")
    if "destination" in config.config:
        mode = config.config["destination"].get("mode", "unknown")
        print(f"  Destination: {mode}")
    if "conversion" in config.config:
        sr = config.config["conversion"].get("sample_rate", "unknown")
        print(f"  Conversion: {sr} Hz")
    if "logging" in config.config:
        level = config.config["logging"].get("level", "unknown")
        print(f"  Logging: {level}")
    print()

    sections = []

    if get_yes_no("Reconfigure source settings?", default=False):
        sections.append("source")

    if get_yes_no("Reconfigure destination settings?", default=False):
        sections.append("destination")

    if get_yes_no("Reconfigure conversion settings?", default=False):
        sections.append("conversion")

    if get_yes_no("Reconfigure logging settings?", default=False):
        sections.append("logging")

    if not sections:
        print("\nNo sections selected. Configuration unchanged.")
        sys.exit(0)

    return sections


def run_interactive_wizard():
    """Run the full interactive configuration wizard with go-back support."""
    print_header("BOUNCE WATCHER CONFIGURATION WIZARD")

    print("This wizard will help you set up Bounce Watcher.")
    print("\nYou can reconfigure at any time by running 'bounce-config' again.")
    print("Type 'b' or 'back' at any prompt to go to the previous step.")

    if not get_yes_no("\nContinue?", default=True):
        print("Configuration cancelled.")
        sys.exit(0)

    # Determine which sections to configure
    sections_to_configure = select_sections_to_configure()

    # Load existing configuration to preserve unmodified sections
    config = Config()
    if config.exists():
        try:
            config.load()
            config_dict = config.config.copy()
        except ConfigError:
            config_dict = {}
    else:
        config_dict = {}

    # Configuration steps as a state machine
    all_steps = [
        ("source", "Source Configuration", configure_source),
        ("destination", "Destination Configuration", configure_destination),
        ("conversion", "Conversion Settings", configure_conversion),
        ("logging", "Logging Settings", configure_logging),
    ]

    # Filter to only steps that need configuration
    steps = [step for step in all_steps if step[0] in sections_to_configure]

    if not steps:
        print("\nNo configuration changes needed.")
        return

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

    # Show summary of what was configured
    all_section_keys = ["source", "destination", "conversion", "logging"]
    modified_sections = [key for key in all_section_keys if key in sections_to_configure]
    preserved_sections = [key for key in all_section_keys if key not in sections_to_configure and key in config_dict]

    if modified_sections:
        print("Modified sections:")
        for key in modified_sections:
            print(f"  ✓ {key.capitalize()}")

    if preserved_sections:
        print("\nPreserved sections:")
        for key in preserved_sections:
            print(f"  ↻ {key.capitalize()} (unchanged)")

    config = Config()
    config.config = config_dict

    try:
        config.save()
        print(f"\n✓ Configuration saved to: {config.config_path}")
    except ConfigError as e:
        print(f"✗ Failed to save configuration: {e}")
        sys.exit(1)

    # Configure LaunchAgent (only if first time or source/destination changed)
    needs_service_restart = any(key in sections_to_configure for key in ["source", "destination"])
    if needs_service_restart or not get_launch_agent_manager().is_installed():
        configure_launchagent(config.config_path)
    else:
        print("\nService configuration unchanged. Restart service to apply changes:")
        print("  launchctl stop com.bouncewatcher.daemon")
        print("  launchctl start com.bouncewatcher.daemon")

    # Done
    print_header("CONFIGURATION COMPLETE")
    if modified_sections:
        print(f"Updated {len(modified_sections)} section(s) successfully!")
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


def uninstall_bounce_watcher():
    """Completely uninstall Bounce Watcher service and configuration."""
    print_header("BOUNCE WATCHER UNINSTALL")

    print("This will completely remove Bounce Watcher from your system:")
    print("  - Stop and unload the background service")
    print("  - Remove the LaunchAgent")
    print("  - Delete the configuration file")
    print("  - Remove all log files")
    print("\nThe Python package will remain installed (use 'pip uninstall bounce-watcher' to remove it)")

    if not get_yes_no("\n⚠️  Are you sure you want to uninstall?", default=False):
        print("Uninstall cancelled.")
        return

    # Track what was removed
    removed_items = []
    errors = []

    # 1. Stop and remove LaunchAgent
    print("\n" + "-" * 80)
    print("Removing LaunchAgent service...")
    print("-" * 80)
    try:
        launch_mgr = get_launch_agent_manager()
        if launch_mgr.is_installed():
            launch_mgr.uninstall()
            removed_items.append(f"LaunchAgent: {launch_mgr.plist_path}")
        else:
            print("No LaunchAgent found (already removed)")
    except LaunchdError as e:
        errors.append(f"Failed to remove LaunchAgent: {e}")
        print(f"✗ {errors[-1]}")

    # 2. Remove configuration file
    print("\n" + "-" * 80)
    print("Removing configuration...")
    print("-" * 80)
    config = Config()
    if config.exists():
        try:
            config.config_path.unlink()
            removed_items.append(f"Configuration: {config.config_path}")
            print(f"✓ Removed: {config.config_path}")
        except Exception as e:
            errors.append(f"Failed to remove config: {e}")
            print(f"✗ {errors[-1]}")
    else:
        print("No configuration file found (already removed)")

    # 3. Remove log files
    print("\n" + "-" * 80)
    print("Removing log files...")
    print("-" * 80)
    config_dir = config.config_path.parent
    if config_dir.exists():
        log_files = list(config_dir.glob("*.log"))
        if log_files:
            for log_file in log_files:
                try:
                    log_file.unlink()
                    removed_items.append(f"Log: {log_file}")
                    print(f"✓ Removed: {log_file}")
                except Exception as e:
                    errors.append(f"Failed to remove {log_file}: {e}")
                    print(f"✗ {errors[-1]}")
        else:
            print("No log files found")

        # Remove config directory if empty
        try:
            if not any(config_dir.iterdir()):
                config_dir.rmdir()
                removed_items.append(f"Directory: {config_dir}")
                print(f"✓ Removed empty directory: {config_dir}")
        except Exception:
            pass  # Directory not empty, that's okay
    else:
        print("Configuration directory not found")

    # 4. Check for old LaunchAgents (cleanup from previous versions)
    print("\n" + "-" * 80)
    print("Checking for old LaunchAgents...")
    print("-" * 80)
    old_labels = [
        "com.payetteforward.bouncewatcher",
        "com.yourusername.bouncewatcher",
    ]
    plist_dir = Path.home() / "Library" / "LaunchAgents"
    for old_label in old_labels:
        old_plist = plist_dir / f"{old_label}.plist"
        if old_plist.exists():
            try:
                # Try to unload first
                subprocess.run(
                    ["launchctl", "unload", str(old_plist)],
                    capture_output=True,
                    check=False  # Don't raise if already unloaded
                )
                old_plist.unlink()
                removed_items.append(f"Old LaunchAgent: {old_plist}")
                print(f"✓ Removed old LaunchAgent: {old_plist}")
            except Exception as e:
                errors.append(f"Failed to remove {old_plist}: {e}")
                print(f"✗ {errors[-1]}")

    # Summary
    print("\n" + "=" * 80)
    print("UNINSTALL SUMMARY")
    print("=" * 80)

    if removed_items:
        print(f"\n✓ Successfully removed {len(removed_items)} item(s):")
        for item in removed_items:
            print(f"  - {item}")

    if errors:
        print(f"\n✗ Encountered {len(errors)} error(s):")
        for error in errors:
            print(f"  - {error}")

    if not errors:
        print("\n✅ Bounce Watcher has been completely uninstalled!")
        print("\nTo remove the Python package:")
        print("  pip3 uninstall bounce-watcher")
        print("\nTo reinstall:")
        print("  pip3 install -e .")
        print("  bounce-config")
    else:
        print("\n⚠️  Uninstall completed with some errors.")
        print("You may need to manually remove remaining files.")

    print()


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
        elif arg in ["--uninstall", "-u"]:
            uninstall_bounce_watcher()
            return
        elif arg in ["--help", "-h"]:
            print("Bounce Watcher Configuration Utility")
            print("\nUsage:")
            print("  bounce-config                Run interactive configuration wizard")
            print("                               (supports selective editing of existing config)")
            print("  bounce-config --status       Show current status")
            print("  bounce-config --test         Test current configuration")
            print("  bounce-config --uninstall    Completely remove Bounce Watcher")
            print("  bounce-config --help         Show this help message")
            print("\nSelective Configuration:")
            print("  If you have an existing configuration, bounce-config will let you:")
            print("  - Edit only specific sections (e.g., just change destination folder)")
            print("  - Keep all other settings unchanged")
            print("  - No need to re-enter server names, passwords, etc.")
            return
        else:
            print(f"Unknown option: {arg}")
            print("Run 'bounce-config --help' for usage information.")
            sys.exit(1)

    # Run interactive wizard
    run_interactive_wizard()


if __name__ == "__main__":
    main()
