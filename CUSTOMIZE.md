# Customizing Bounce Watcher

This document explains how to customize Bounce Watcher for your specific needs while keeping your personal configuration separate from the codebase.

## Quick Start

The easiest way to customize is using the interactive wizard:

```bash
bounce-config
```

This will guide you through all configuration options and save to `~/.config/bounce-watcher/config.toml`.

## Configuration File

Your personal configuration is stored in:
```
~/.config/bounce-watcher/config.toml
```

This file is **not** tracked by git, so your personal settings remain private.

## Example Configuration

See `config.example.toml` for a complete example with comments explaining each option.

## Common Customizations

### Change Source Folders

Edit your config file:
```toml
[source]
mode = "specific_folders"
folders = [
    "/Volumes/My Drive 1",
    "/Volumes/My Drive 2"
]
```

Or use the wizard:
```bash
bounce-config
```

### Change Destination

**For iCloud:**
```toml
[destination]
mode = "icloud"
icloud_path = "/Users/yourusername/Library/Mobile Documents/com~apple~CloudDocs/Downloads"
```

**For NAS:**
```toml
[destination]
mode = "nas"
nas_url = "smb://your-server.local/share"
nas_username = "your-username"
nas_mount_point = "/Volumes/YourNAS"
```

Then store your password in keychain:
```bash
security add-generic-password -a your-username -s your-server.local -w 'your-password' -U
```

**For Custom Folder:**
```toml
[destination]
mode = "custom"
custom_path = "/Users/yourusername/Music/Converted Mixes"
```

### Adjust Conversion Settings

```toml
[conversion]
sample_rate = 44100  # or 48000, 96000, etc.
stability_check_interval = 3  # increase if files are large
stability_checks_required = 5  # increase for more certainty
```

### Change Log Location

```toml
[logging]
log_file = "/path/to/your/logs/bounce_watcher.log"
level = "DEBUG"  # or "INFO", "WARNING", "ERROR"
```

## Advanced Customizations

### Modify Conversion Script

The audio conversion is handled by `scripts/convert_mix.sh`. You can modify:

- AAC bitrate (default: 256 kbps)
- Sample rate conversion
- Sound Check settings
- Output format

### Custom Mix File Detection

```toml
[source]
mix_file_prefix = "master"  # detect "master_*.wav" instead of "mix_*.wav"
audio_files_folder = "Bounces"  # if your sessions use different folder name
```

### Multiple Configurations

You can maintain multiple configurations and switch between them:

```bash
# Save current config
cp ~/.config/bounce-watcher/config.toml ~/.config/bounce-watcher/config.studio.toml

# Create mobile config
bounce-config
# Configure for mobile setup
mv ~/.config/bounce-watcher/config.toml ~/.config/bounce-watcher/config.mobile.toml

# Switch between configs
cp ~/.config/bounce-watcher/config.studio.toml ~/.config/bounce-watcher/config.toml
# or
cp ~/.config/bounce-watcher/config.mobile.toml ~/.config/bounce-watcher/config.toml
```

## Keeping Your Setup Private

When contributing to the project or sharing your setup:

1. **Never commit your personal config** - it's in `.gitignore`
2. **Use environment variables or config files** for sensitive data
3. **Keep passwords in macOS Keychain** - never in config files
4. **Share `config.example.toml`** modifications, not your actual config

## Testing Your Configuration

```bash
# Test configuration validity
bounce-config --test

# Check status
bounce-config --status

# Run in foreground (for debugging)
bounce-watcher
```

## Upgrading

When upgrading Bounce Watcher:

1. Your config file is preserved (it's outside the codebase)
2. Check `CHANGELOG.md` for configuration changes
3. Run `bounce-config --test` to validate your config
4. Update your config if new options are available

## Troubleshooting

**Config not found:**
```bash
bounce-config  # Run wizard to create
```

**Invalid config:**
```bash
bounce-config --test  # See what's wrong
```

**Reset to defaults:**
```bash
rm ~/.config/bounce-watcher/config.toml
bounce-config  # Run wizard again
```

## Support

For help with configuration:
1. Check the main `README.md`
2. Look at `config.example.toml`
3. Run `bounce-config --help`
4. Check logs for specific errors
