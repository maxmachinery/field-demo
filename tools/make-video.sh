#!/usr/bin/env bash
# Turn the Playwright .webm recordings into shareable files.
#   tools/record.py  ->  video/raw/{desktop,mobile}.webm
#   this script      ->  video/field-demo-{desktop,mobile}.mp4  +  video/field-demo.gif
# video/ is gitignored.
set -euo pipefail
cd "$(dirname "$0")/.."
raw=video/raw
out=video

[ -f "$raw/desktop.webm" ] || { echo "missing $raw/desktop.webm - run: python3 tools/record.py" >&2; exit 1; }

mp4 () { # $1 = name
  ffmpeg -y -loglevel error -i "$raw/$1.webm" \
    -vf "scale=trunc(iw/2)*2:trunc(ih/2)*2,fps=30" \
    -c:v libx264 -preset slow -crf 20 -pix_fmt yuv420p -movflags +faststart -an \
    "$out/field-demo-$1.mp4"
  echo "wrote $out/field-demo-$1.mp4 ($(du -h "$out/field-demo-$1.mp4" | cut -f1))"
}

mp4 desktop
[ -f "$raw/mobile.webm" ] && mp4 mobile

# GIF: 10 fps, 820px wide, shared palette. Keeps the 66 s loop under 8 MB.
pal=$(mktemp -t fd-palette).png
ffmpeg -y -loglevel error -i "$raw/desktop.webm" \
  -vf "fps=10,scale=820:-1:flags=lanczos,palettegen=max_colors=128" "$pal"
ffmpeg -y -loglevel error -i "$raw/desktop.webm" -i "$pal" \
  -lavfi "fps=10,scale=820:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=3" \
  "$out/field-demo.gif"
rm -f "$pal"

size=$(du -k "$out/field-demo.gif" | cut -f1)
echo "wrote $out/field-demo.gif (${size}K)"
[ "$size" -lt 8192 ] || echo "WARNING: gif is over 8 MB - drop fps or width" >&2
