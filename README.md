# Pro Tools Bounce Watcher

[![macOS](https://img.shields.io/badge/macOS-10.15+-blue.svg)](https://www.apple.com/macos)
[![Python](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

> **Note:** This tool is designed exclusively for macOS and uses macOS-specific features like FSEvents, LaunchAgents, Keychain, and Apple's `afconvert`. It will not work on Windows or Linux.

Automatically monitors Pro Tools session folders and converts new mix files to high-quality M4A format for easy sharing via iCloud, network storage, or custom folders.

**Professional-grade conversion following [Apple Digital Masters](https://www.apple.com/apple-music/apple-digital-masters/) best practices** - uses Apple's recommended two-step pipeline with Sound Check integration for broadcast-ready audio.

## What's New in v2.0

- **Intelligent Hot-Plug Monitoring**: Automatically detects and monitors external drives as they're connected/disconnected - no restart required!
- **Flexible Source Configuration**: Choose between specific folders or automatic external drive detection
- **NAS Support**: Save converted files to network storage (SMB) with secure keychain authentication
- **Interactive Configuration Wizard**: Easy setup with `bounce-config` command
- **Professional Package Structure**: Installable Python package with modular architecture
- **Smart Drive Filtering**: Automatically detects and filters suitable external drives
- **LaunchAgent Management**: Built-in service installation and management
- **TOML Configuration**: Human-readable configuration files

## Features

- **Automatic monitoring**: Watches specified folders or all external drives for new Pro Tools mix files
- **Smart file detection**: Only processes files beginning with "mix" in "Audio Files" folders
- **Stability checking**: Waits for files to finish writing before processing
- **Apple Digital Masters compliant**: Professional two-step conversion pipeline following Apple's best practices
- **High-quality conversion**: 256 kbps AAC with Sound Check, maximum quality settings (-q 127)
- **Flexible destinations**: Save to iCloud Downloads, network storage (NAS), or custom folders
- **Organized output**: Creates subdirectories based on Pro Tools session names
- **Clean intermediate files**: All temporary CAF files are stored in system temp and cleaned up automatically
- **Notifications**: macOS notifications for conversion status
- **Detailed logging**: Comprehensive logs for troubleshooting
- **Background service**: Runs automatically on login via LaunchAgent

## Requirements

- **macOS 10.15 (Catalina) or higher** (required)
- **Python 3.9 or higher**
- Pro Tools session folders with standard "Audio Files" structure
- Administrator access for LaunchAgent installation (optional, for background service)

## Installation

### 1. Clone the Repository

```bash
# Clone to your preferred location
git clone https://github.com/payetteforward/bounce-watcher.git
cd bounce-watcher
```

### 2. Install Dependencies

```bash
# Using pip (recommended)
pip3 install -r requirements.txt

# Or using pip with user install
pip3 install --user -r requirements.txt
```

### 3. Install the Package

```bash
# Development mode (recommended for easy updates)
pip3 install -e .

# Or standard installation
pip3 install .
```

### 4. Run Configuration Wizard

```bash
bounce-config
```

The interactive wizard will guide you through:
1. **Source Configuration**: Choose specific folders or all external drives
2. **Destination Configuration**: Choose iCloud, NAS (with keychain password storage), or custom folder
3. **Conversion Settings**: Sample rate and stability checking parameters
4. **Logging Settings**: Log file location and verbosity
5. **LaunchAgent Setup**: Automatic background service installation

After configuration, the service will start automatically and monitor your folders in the background.

## Configuration

### Interactive Configuration

The easiest way to configure Bounce Watcher is using the interactive wizard:

```bash
bounce-config
```

**Selective Editing:** If you already have a configuration and just want to change one thing (like the destination folder), the wizard will offer to edit only specific sections. No need to re-enter everything!

Example workflow:
1. Run `bounce-config`
2. Choose "Edit specific sections only"
3. Select only "Reconfigure destination settings?" → Yes
4. Change your destination folder
5. Done! All other settings (source, NAS passwords, etc.) remain unchanged.

### Configuration File

Configuration is stored in `~/.config/bounce-watcher/config.toml`:

```toml
[source]
mode = "specific_folders"  # or "all_external_drives"
folders = ["/Volumes/External SSD", "/Volumes/Studio Drive"]
audio_files_folder = "Audio Files"
mix_file_prefix = "mix"

[destination]
mode = "icloud"  # or "nas" or "custom"
icloud_path = "/Users/yourusername/Library/Mobile Documents/com~apple~CloudDocs/Downloads"
nas_url = "smb://your-nas-server.local/music"
nas_username = "yourusername"
nas_mount_point = "/Volumes/Music"
custom_path = "/Users/yourusername/Music/Bounce Watcher"

[conversion]
sample_rate = 48000
stability_check_interval = 2
stability_checks_required = 3

[logging]
log_file = "/Users/yourusername/scripts/bounce-watcher/bounce_watcher.log"
level = "INFO"
```

### NAS Configuration

When using NAS mode, the password is stored securely in macOS Keychain:

```bash
# The configuration wizard will prompt for the password
bounce-config

# Or add manually to keychain
security add-generic-password \
  -a yourusername \
  -s your-nas-server.local \
  -w YOUR_PASSWORD \
  -U
```

## Usage

### Check Status

```bash
bounce-config --status
```

Shows:
- Configuration file location and validity
- Current source and destination modes
- LaunchAgent installation status
- Service running status (PID if active)

### Test Configuration

```bash
bounce-config --test
```

Tests:
- Configuration file validity
- Source accessibility (folders exist or drives detected)
- Destination accessibility (iCloud path or NAS connection)

### Running the Service

The service runs automatically as a LaunchAgent after installation. To manage it:

```bash
# Check if running
launchctl list | grep bouncewatcher

# Stop the service
launchctl stop com.bouncewatcher.daemon

# Unload the service
launchctl unload ~/Library/LaunchAgents/com.bouncewatcher.daemon.plist

# Reload the service
launchctl load ~/Library/LaunchAgents/com.bouncewatcher.daemon.plist
```

### Running Manually (for testing)

```bash
bounce-watcher
```

Press `Ctrl+C` to stop.

## Source Modes

### Specific Folders Mode

Watches only the folders you specify. Good for:
- Monitoring specific Pro Tools projects
- Controlled, predictable behavior
- Faster scanning with fewer folders

Example configuration:
```toml
[source]
mode = "specific_folders"
folders = ["/Volumes/External SSD", "/Volumes/Studio Drive"]
```

### All External Drives Mode

Automatically detects and watches all connected external drives with **intelligent hot-plug monitoring**. Good for:
- Multiple external drives with Pro Tools sessions
- Dynamic drive connections/disconnections
- No manual folder management
- Working with frequently connected/disconnected drives

**Dynamic Drive Monitoring:**
- Automatically detects when external drives are connected
- Immediately starts monitoring new drives
- Gracefully stops monitoring when drives are disconnected
- Sends notifications when drives are added/removed
- No restart required for drive changes

Smart filtering automatically excludes:
- Drives smaller than 1 GB
- FAT/FAT32 filesystems (keeps APFS/HFS+)
- Time Machine backup volumes
- System volumes

Example configuration:
```toml
[source]
mode = "all_external_drives"
folders = []  # Not used in this mode
```

**How it works:**
1. On startup, detects all currently connected external drives
2. Continuously monitors `/Volumes` for new drives being mounted
3. When a new drive is detected, validates it with smart filtering
4. Automatically adds valid drives to the watch list
5. When a drive is unmounted, gracefully removes it from watching
6. You'll see notifications when drives are added or removed

## Destination Modes

### iCloud Downloads Mode

Saves converted files to your iCloud Downloads folder for easy access across all your Apple devices.

Example configuration:
```toml
[destination]
mode = "icloud"
icloud_path = "/Users/yourusername/Library/Mobile Documents/com~apple~CloudDocs/Downloads"
```

### NAS Mode

Saves converted files to network storage via SMB. The NAS is automatically mounted when needed.

Example configuration:
```toml
[destination]
mode = "nas"
nas_url = "smb://your-nas-server.local/music"
nas_username = "yourusername"
nas_mount_point = "/Volumes/Music"
```

Password is stored in macOS Keychain for security.

### Custom Folder Mode

Saves converted files to any folder you specify on your Mac or mounted network drives.

Example configuration:
```toml
[destination]
mode = "custom"
custom_path = "/Users/yourusername/Music/Bounce Watcher"
```

Perfect for local folders, external drives, or manually-mounted network shares.

## How It Works

1. **Monitoring**: Watches configured folders or detected external drives recursively
2. **Detection**: When a new file starting with "mix" appears in an "Audio Files" folder, it's detected
3. **Stability Check**: Monitors file size every 2 seconds until stable (same size 3 times in a row)
4. **Conversion**: Once stable, converts using Apple's recommended two-step process:
   - Step 1: Convert to CAF with Sound Check (in temp directory)
   - Step 2: Convert CAF to 256 kbps M4A with Sound Check
5. **Organization**: Final M4A is placed in configured destination under session-named subdirectory
6. **Cleanup**: Intermediate CAF files are automatically deleted
7. **Notification**: macOS notification sent on completion or error

## File Structure

Expected Pro Tools session structure:
```
/Volumes/External SSD/
└── My Pro Tools Session/
    └── Audio Files/
        ├── mix_01.wav          ← Will be processed
        ├── mix_final.wav       ← Will be processed
        ├── Mix-Master.wav      ← Will be processed (case-insensitive)
        └── guitar_track.wav    ← Will be ignored
```

Output structure (iCloud mode):
```
~/Library/Mobile Documents/com~apple~CloudDocs/Downloads/
└── My Pro Tools Session/
    ├── mix_01.m4a
    ├── mix_final.m4a
    └── Mix-Master.m4a
```

Output structure (NAS mode):
```
/Volumes/Music/
└── My Pro Tools Session/
    ├── mix_01.m4a
    ├── mix_final.m4a
    └── Mix-Master.m4a
```

Output structure (custom folder mode):
```
/Users/yourusername/Music/Bounce Watcher/
└── My Pro Tools Session/
    ├── mix_01.m4a
    ├── mix_final.m4a
    └── Mix-Master.m4a
```

## Architecture

```
bounce-watcher/
├── bounce_watcher/              # Main package
│   ├── __init__.py
│   ├── main.py                  # Entry point
│   ├── config.py                # Configuration management
│   ├── sources.py               # Drive detection & source management
│   ├── destinations.py          # iCloud & NAS handling
│   ├── watcher.py               # File watching logic
│   ├── converter.py             # Conversion orchestration
│   ├── launchd.py              # LaunchAgent management
│   ├── configure.py             # Configuration wizard
│   └── utils.py                 # Logging, notifications
├── scripts/
│   └── convert_mix.sh           # Audio conversion script
├── pyproject.toml               # Package configuration
├── requirements.txt             # Dependencies
└── README.md                    # This file
```

## Logs

- **Main log**: Configured in `config.toml` (default: `bounce_watcher.log`)
- **Service logs** (when using LaunchAgent):
  - `stdout.log` - Standard output
  - `stderr.log` - Error output

View logs in real-time:
```bash
# Main log
tail -f ~/scripts/bounce-watcher/bounce_watcher.log

# Service stderr
tail -f ~/scripts/bounce-watcher/stderr.log
```

## Troubleshooting

### No configuration file found

**Solution**: Run `bounce-config` to create your configuration.

### The watcher isn't detecting files

1. Check configuration: `bounce-config --test`
2. Verify watch roots exist (specific folders mode)
3. Check external drives are connected (all external drives mode)
4. Verify "Audio Files" folder name matches (case-sensitive)
5. Check logs for permission errors
6. Ensure drives are mounted

### Conversion fails

1. Check main log for details
2. Verify `afconvert` is available: `which afconvert`
3. Test conversion manually:
   ```bash
   scripts/convert_mix.sh /path/to/mix_file.wav /path/to/output 48000
   ```
4. Check input file is valid audio format

### Files aren't appearing in destination

**iCloud mode:**
1. Verify iCloud Drive is enabled and syncing
2. Check the path exists: `ls -la ~/Library/Mobile\ Documents/com~apple~CloudDocs/Downloads`
3. Look for errors in log

**NAS mode:**
1. Test NAS connection: `bounce-config --test`
2. Verify password is in keychain:
   ```bash
   security find-generic-password -a yourusername -s your-nas-server.local
   ```
3. Check NAS is accessible: `ping your-nas-server.local`
4. Try mounting manually:
   ```bash
   mkdir -p /Volumes/Music
   mount_smbfs //yourusername@your-nas-server.local/music /Volumes/Music
   ```

### Service won't start

1. Check service status: `bounce-config --status`
2. View error log: `cat ~/scripts/bounce-watcher/stderr.log`
3. Test configuration: `bounce-config --test`
4. Try running manually: `bounce-watcher`
5. Check LaunchAgent plist exists: `ls -la ~/Library/LaunchAgents/com.bouncewatcher.daemon.plist`

### High CPU usage

1. Increase `stability_check_interval` in config (checks less frequently)
2. Reduce number of watch roots (specific folders mode)
3. Switch from "all external drives" to "specific folders" mode if monitoring too many drives

## Migrating from v1.0

If you're upgrading from v1.0:

1. **Navigate to your installation directory**:
   ```bash
   cd bounce-watcher  # or wherever you cloned it
   ```

2. **Pull the latest changes**:
   ```bash
   git pull
   ```

3. **Update dependencies and reinstall**:
   ```bash
   pip3 install -r requirements.txt
   pip3 install -e .
   ```

4. **Stop and remove the old service** (if it exists):
   ```bash
   launchctl unload ~/Library/LaunchAgents/com.payetteforward.bouncewatcher.plist 2>/dev/null || true
   rm ~/Library/LaunchAgents/com.payetteforward.bouncewatcher.plist 2>/dev/null || true
   ```

5. **Run the configuration wizard**:
   ```bash
   bounce-config
   ```

   Your old settings from `bounce_watcher.py` will be migrated to the new TOML config format.

6. **The new service will be installed automatically** by the wizard.

7. **Your old files are preserved** - the new package structure doesn't overwrite them.

## Advanced Configuration

### Changing the conversion sample rate

Edit `~/.config/bounce-watcher/config.toml`:
```toml
[conversion]
sample_rate = 44100  # or 96000, etc.
```

Then restart the service:
```bash
launchctl stop com.bouncewatcher.daemon
launchctl start com.bouncewatcher.daemon
```

### Changing the AAC bitrate

Edit `scripts/convert_mix.sh`:
```bash
-b 256000  # Change to desired bitrate (e.g., 320000 for 320 kbps)
```

### Custom mix file prefix

Edit `~/.config/bounce-watcher/config.toml`:
```toml
[source]
mix_file_prefix = "master"  # Will match master_01.wav, MASTER-final.wav, etc.
```

### Custom audio folder name

If your Pro Tools sessions use a different folder name:

```toml
[source]
audio_files_folder = "Bounces"  # or "Mixdown", "Output", etc.
```

## Technical Details

### Conversion Pipeline

Bounce Watcher implements **Apple Digital Masters best practices** for professional-grade audio conversion, following the specifications outlined in Apple's official [Apple Digital Masters documentation](https://www.apple.com/apple-music/apple-digital-masters/).

#### Two-Step Mastered for iTunes Pipeline

The conversion uses Apple's recommended two-step pipeline for optimal quality:

**Step 1: Source → CAF (Intermediate Format)**
- Format: 32-bit float Little-Endian (LEF32)
- Container: Core Audio Format (CAF)
- Sound Check: Generated and embedded
- Sample Rate Conversion (if needed):
  - Algorithm: `bats` (Best Audio Time Stretching)
  - Quality: `-r 127` (maximum quality)
  - Triggered when source > 48 kHz

**Step 2: CAF → AAC M4A (Distribution Format)**
- Codec: AAC (Advanced Audio Coding)
- Bitrate: 256 kbps CBR
- Quality: `-q 127` (maximum)
- Strategy: `-s 2` (pgcm 2 - optimal for music)
- Sound Check: Read from CAF and embedded
- Container: M4A (MPEG-4 Audio)

#### Compliance with Apple Digital Masters Standards

✅ **Two-step conversion process** - Separates SRC from encoding
✅ **Sound Check integration** - Consistent playback levels
✅ **High-quality SRC** - Uses Apple's `bats` algorithm
✅ **Maximum quality settings** - `-q 127` and `-r 127`
✅ **256 kbps AAC** - Apple's recommended bitrate for distribution
✅ **32-bit float intermediate** - Preserves dynamic range
✅ **Proper strategy flag** - `pgcm 2` for music content

#### Why This Pipeline?

- **Professional Quality**: Meets Apple Music's distribution standards
- **Sound Check**: Enables consistent playback volume across tracks (iTunes/Music app)
- **Two-step process**: Separates sample rate conversion from AAC encoding for best quality
- **High quality SRC**: Apple's proprietary "bats" algorithm for sample rate conversion
- **Clean workflow**: Intermediate files isolated in system temp, automatically cleaned up
- **Future-proof**: Compatible with Apple Music, iTunes Match, and iCloud Music Library

This implementation ensures your mixes meet professional streaming quality standards while maintaining the highest possible fidelity during conversion.

### External Drive Detection

Uses `diskutil` to detect external drives with smart filtering:
- Only physical external drives (no disk images)
- Only APFS/HFS+ filesystems
- Only drives >= 1 GB
- Excludes Time Machine volumes
- Excludes system volumes

### NAS Authentication

- Password stored securely in macOS Keychain
- Uses `security` command for keychain access
- NAS auto-mounted when needed using `mount_smbfs`
- Graceful reconnection if connection drops

## Commands Reference

```bash
# Configuration
bounce-config                    # Run interactive wizard
bounce-config --status           # Show current status
bounce-config --test             # Test configuration
bounce-config --help             # Show help

# Running the watcher
bounce-watcher                   # Run manually (foreground)

# Service management
launchctl list | grep bounce     # Check if service is running
launchctl stop com.bouncewatcher.daemon
launchctl start com.bouncewatcher.daemon
```

## Platform Compatibility

**macOS Only** - This tool is designed exclusively for macOS and will not work on other platforms because it uses:
- **FSEvents**: macOS file system event monitoring API
- **LaunchAgents**: macOS background service management system
- **Keychain**: macOS secure credential storage
- **afconvert**: Apple's audio conversion utility (pre-installed on macOS)
- **osascript**: AppleScript for mounting network volumes
- **/Volumes**: macOS mount point convention

If you're looking for a cross-platform audio conversion tool, you may want to explore alternatives built with platform-independent libraries.

## License

MIT License - See [LICENSE](LICENSE) file for details.

This project is free and open source. Use, modify, and distribute as needed.

## Support

For issues:
1. Check `bounce-config --status` and `--test`
2. Review logs (location shown in status)
3. Most issues are related to:
   - Configuration errors
   - File permissions
   - Incorrect paths
   - External drives not mounted
   - iCloud Drive sync issues
   - NAS connectivity problems
