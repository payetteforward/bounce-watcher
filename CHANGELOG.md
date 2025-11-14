# Changelog

All notable changes to Bounce Watcher will be documented in this file.

## [2.0.0] - 2025-11-14

### Added
- **Custom Folder Destination**: Third destination option for saving to any custom folder
- **Intelligent Hot-Plug Monitoring**: Automatic detection and monitoring of external drives as they connect/disconnect
- **Dynamic Drive Management**: No restart needed when drives are added or removed
- **NAS Support**: SMB network storage with secure keychain authentication
- **Interactive Configuration Wizard**: `bounce-config` command for easy setup
- **Professional Package Structure**: Installable Python package with modular architecture
- **Smart Drive Filtering**: APFS/HFS+ only, excludes FAT, Time Machine, small drives
- **LaunchAgent Management**: Built-in service installation and management
- **TOML Configuration**: Human-readable config files in `~/.config/bounce-watcher/`
- **Adaptive Energy Optimization**: Event-driven polling with idle detection
- **Source Mode Options**: Choose specific folders or all external drives

### Changed
- Refactored from monolithic script to modular package structure
- Optimized stability checking for minimal CPU/battery usage
- Improved error handling and logging throughout
- Enhanced notifications with drive connect/disconnect events

### Performance
- ~95% reduction in CPU wake-ups when idle
- Event-driven architecture instead of continuous polling
- Adaptive polling intervals (2s active, 30-60s idle)
- Uses native macOS FSEvents for zero-overhead file watching

### Technical
- Python 3.9+ required
- Dependencies: watchdog, tomli (Python <3.11), tomli-w
- Modular architecture: config, sources, destinations, watcher, converter, launchd, utils
- Comprehensive error handling and validation
- macOS-native integration (FSEvents, Keychain, LaunchAgents)

## [1.0.0] - 2025-11-13

### Initial Release
- Basic file watching for Pro Tools mix files
- Automatic WAV/AIFF to M4A conversion
- iCloud Downloads integration
- Hard-coded configuration
- Simple LaunchAgent setup
