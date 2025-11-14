"""
Main entry point for Bounce Watcher.

Orchestrates all components and runs the file watching service.
"""

import sys
from pathlib import Path

from .config import load_config, ConfigError
from .sources import get_source_manager
from .destinations import get_destination_manager, DestinationError
from .converter import get_audio_converter, ConversionError
from .watcher import BounceWatcher
from .utils import setup_logging, send_notification


def main():
    """
    Main entry point for bounce-watcher daemon.

    Loads configuration, initializes components, and starts file watching.
    """
    try:
        # Load configuration
        try:
            config = load_config()
        except ConfigError as e:
            print(f"Configuration error: {e}")
            print("\nPlease run 'bounce-config' to set up your configuration.")
            sys.exit(1)

        # Check if config file exists
        if not config.exists():
            print("No configuration file found.")
            print("\nPlease run 'bounce-config' to set up your configuration.")
            sys.exit(1)

        # Set up logging
        log_config = config.config.get("logging", {})
        log_file = log_config.get("log_file")
        log_level = log_config.get("level", "INFO")
        logger = setup_logging(log_file, log_level)

        logger.info("Starting Bounce Watcher")
        logger.debug(f"Configuration loaded from: {config.config_path}")

        # Initialize source manager
        try:
            source_manager = get_source_manager(config.config)
            watch_roots = source_manager.get_watch_roots()
            logger.info(f"Source mode: {source_manager.mode}")
            logger.info(f"Watch roots: {watch_roots}")
        except Exception as e:
            logger.error(f"Failed to initialize source manager: {e}")
            send_notification(
                "Bounce Watcher Error",
                f"Failed to initialize sources: {str(e)}"
            )
            sys.exit(1)

        # Initialize destination manager
        try:
            destination_manager = get_destination_manager(config.config)
            logger.info(f"Destination mode: {destination_manager.mode}")

            # Test destination
            if not destination_manager.test_destination():
                logger.error("Destination is not accessible")
                send_notification(
                    "Bounce Watcher Error",
                    "Destination is not accessible. Please check configuration."
                )
                sys.exit(1)
        except DestinationError as e:
            logger.error(f"Failed to initialize destination manager: {e}")
            send_notification(
                "Bounce Watcher Error",
                f"Failed to initialize destination: {str(e)}"
            )
            sys.exit(1)

        # Initialize audio converter
        try:
            script_dir = Path(__file__).parent.parent
            audio_converter = get_audio_converter(config.config, script_dir)
            logger.info(f"Audio converter initialized: {audio_converter}")
        except ConversionError as e:
            logger.error(f"Failed to initialize audio converter: {e}")
            send_notification(
                "Bounce Watcher Error",
                f"Failed to initialize converter: {str(e)}"
            )
            sys.exit(1)

        # Get configuration values
        source_config = config.config.get("source", {})
        audio_folder_name = source_config.get("audio_files_folder", "Audio Files")
        mix_prefix = source_config.get("mix_file_prefix", "mix")
        source_mode = source_config.get("mode", "specific_folders")

        conv_config = config.config.get("conversion", {})
        stability_interval = conv_config.get("stability_check_interval", 2)
        stability_checks = conv_config.get("stability_checks_required", 3)

        # Create and run watcher
        watcher = BounceWatcher(
            watch_roots=watch_roots,
            audio_folder_name=audio_folder_name,
            mix_prefix=mix_prefix,
            destination_manager=destination_manager,
            audio_converter=audio_converter,
            source_manager=source_manager,
            source_mode=source_mode,
            stability_interval=stability_interval,
            stability_checks=stability_checks
        )

        # Send startup notification
        send_notification(
            "Bounce Watcher",
            "Bounce Watcher is now running",
            subtitle=f"Watching {len(watch_roots)} location(s)"
        )

        # Run watcher (blocking)
        watcher.run()

    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        send_notification(
            "Bounce Watcher Error",
            f"Unexpected error: {str(e)}"
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
