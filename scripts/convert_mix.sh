#!/bin/zsh
# Bounce Watcher Converter - Apple Digital Masters Compliant
#
# Implements the two-step conversion pipeline recommended in Apple's
# "Mastered for iTunes" / Apple Digital Masters documentation:
# https://www.apple.com/apple-music/apple-digital-masters/
#
# Step 1: Source → CAF (32-bit float, Sound Check generation)
# Step 2: CAF → AAC M4A (256 kbps, Sound Check embedded)
#
# This ensures professional-grade audio quality suitable for streaming
# and distribution via Apple Music, iTunes Match, and iCloud Music Library.
#
# Usage: convert_mix.sh <input_file> <output_directory> [sample_rate]

set -euo pipefail

# Ensure common paths (Homebrew included)
export PATH="/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin:/usr/local/bin:$PATH"

# Check arguments
if [[ $# -lt 2 || $# -gt 3 ]]; then
  echo "Usage: $0 <input_file> <output_directory> [sample_rate]" >&2
  exit 1
fi

inpath="$1"
target_dir="$2"
final_sample_rate="${3:-48000}"  # Use third argument or default to 48000

# Validate input file exists
if [[ ! -f "$inpath" ]]; then
  echo "Error: Input file does not exist: $inpath" >&2
  exit 1
fi

# Make sure target directory exists
mkdir -p "$target_dir"

# Create a temporary directory for all intermediate files (CAF, etc.)
tmp_dir="$(mktemp -d -t apple_aac_conv.XXXXXXXX)"
# Ensure temp directory is removed when the script exits
trap 'rm -rf "$tmp_dir"' EXIT

notify() {
  # Safe notification (escapes quotes for AppleScript)
  local title="$1" msg="$2"
  /usr/bin/osascript -e "display notification \"${msg//\"/\\\"}\" with title \"${title//\"/\\\"}\""
}

unique_outfile() {
  # $1 = directory, $2 = base name (no ext), $3 = extension (m4a / caf)
  local dir="$1" base="$2" ext="$3" candidate n=1
  candidate="${dir}/${base}.${ext}"
  while [[ -e "$candidate" ]]; do
    candidate="${dir}/${base} (AAC ${n}).${ext}"
    (( n++ ))
  done
  print -r -- "$candidate"
}

convert_with_afconvert_apple() {
  # Apple Digital Masters compliant 2-step pipeline:
  #
  # Step 1: Source → CAF with Sound Check
  #   - 32-bit float Little-Endian format (LEF32)
  #   - Sound Check metadata generation
  #   - High-quality SRC if downsampling needed (bats algorithm, -r 127)
  #
  # Step 2: CAF → AAC M4A with Sound Check
  #   - 256 kbps AAC encoding
  #   - Maximum quality (-q 127)
  #   - Strategy 2 (pgcm, optimal for music)
  #   - Sound Check metadata embedded
  #
  # $1 = input path
  # $2 = intermediate CAF path (in temp dir)
  # $3 = final M4A path (in target_dir)
  # $4 = final sample rate (e.g., 48000)

  local inpath="$1" cafpath="$2" outpath="$3" target_sr="$4"
  local sr_line sr_int

  # Try to detect source sample rate
  if sr_line="$(/usr/bin/afinfo "$inpath" 2>/dev/null | awk '/sample rate/ {print $3; exit}')"; then
    sr_int="${sr_line%.*}"  # strip any decimals
  else
    sr_int=""
  fi

  # Step 1: LPCM -> CAF, adding Sound Check
  # If source sample rate > final production rate, use Apple's downsample recipe.
  if [[ -n "${sr_int:-}" && "$sr_int" -gt "$target_sr" ]]; then
    # Downsample using optimal SRC with bats + -r 127
    /usr/bin/afconvert "$inpath" \
      -d "LEF32@${target_sr}" \
      -f caff \
      --soundcheck-generate \
      --src-complexity bats \
      -r 127 \
      "$cafpath" \
      || return 1
  else
    # Already at (or below) final production rate: simple CAF + Sound Check
    /usr/bin/afconvert "$inpath" "$cafpath" \
      -d 0 \
      -f caff \
      --soundcheck-generate \
      || return 1
  fi

  # Step 2: CAF -> 256 kbps AAC M4A, reading Sound Check info
  /usr/bin/afconvert "$cafpath" \
    -d aac \
    -f m4af \
    -u pgcm 2 \
    --soundcheck-read \
    -b 256000 \
    -q 127 \
    -s 2 \
    "$outpath" \
    || return 1
}

convert_with_ffmpeg() {
  # Fallback: High quality AAC via ffmpeg (320 kbps CBR)
  local inpath="$1" outpath="$2"
  /usr/bin/env ffmpeg -hide_banner -loglevel error -y -i "$inpath" \
    -c:a aac -b:a 320k -movflags +faststart "$outpath"
}

# Process the single input file
base="$(basename "$inpath")"
name_without_ext="${base%.*}"

# Final M4A goes into the target directory
outfile="$(unique_outfile "$target_dir" "$name_without_ext" "m4a")"

# Intermediate CAF lives only in the temp directory
caf_file="${tmp_dir}/${name_without_ext}-intermediate.caf"

# Apple-recommended afconvert pipeline
if convert_with_afconvert_apple "$inpath" "$caf_file" "$outfile" "$final_sample_rate" 2> /tmp/bounce_watcher_conv_err.log; then
  # Remove intermediate CAF after successful conversion
  rm -f "$caf_file" 2>/dev/null || true
  notify "Bounce Watcher" "Converted: $(basename "$inpath") → $(basename "$outfile")"
  echo "✓ Successfully converted to: $outfile"
  exit 0
fi

# If afconvert pipeline fails, clean up any existing CAF
rm -f "$caf_file" 2>/dev/null || true

# Fallback to ffmpeg if installed
if command -v ffmpeg >/dev/null 2>&1; then
  if convert_with_ffmpeg "$inpath" "$outfile" 2> /tmp/bounce_watcher_conv_err.log; then
    notify "Bounce Watcher (ffmpeg)" "Converted: $(basename "$inpath") → $(basename "$outfile")"
    echo "✓ Successfully converted (ffmpeg) to: $outfile"
    exit 0
  fi
fi

# If both failed
notify "Bounce Watcher - Error" "Failed to convert: $(basename "$inpath")"
echo "✗ Conversion failed for: $inpath" >&2
echo "  See /tmp/bounce_watcher_conv_err.log for details" >&2
exit 1
